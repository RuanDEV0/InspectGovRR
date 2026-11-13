"""Importa o ano por meses e publica o conjunto quando todos passam na conferência."""

from contextlib import contextmanager, nullcontext
from datetime import datetime
from decimal import Decimal

from django.db import connection, transaction
from django.utils import timezone

from integrations.fiplan_api.client import FiplanClient
from portal.formatting import LOCAL_TIME_ZONE

from .mappers import normalize
from .models import Payment, PaymentSnapshot

BATCH_SIZE = 1000
STATUS = PaymentSnapshot.Status


class PaymentSyncError(ValueError):
    pass


@contextmanager
def year_lock(year):
    if connection.vendor != 'postgresql':
        yield
        return

    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s, %s)', [165479, year])
        acquired = cursor.fetchone()[0]
    if not acquired:
        raise PaymentSyncError('Já há uma coleta de pagamentos para este ano.')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s, %s)', [165479, year])


def filters_for_month(year, month):
    return {'anoInicio': year, 'anoFinal': year, 'mesInicio': month, 'mesFinal': month}


def page_count(payload):
    if not isinstance(payload, dict):
        raise ValueError('Listagem de pagamentos inválida.')
    count = payload.get('totalElements')
    rows = payload.get('content')
    if (type(count) is not int or count < 0 or payload.get('number') != 0
            or not isinstance(rows, list) or len(rows) != min(1, count)):
        raise ValueError('Contagem inválida na listagem de pagamentos.')
    return count


def collect_month(api, snapshot, month):
    filters = filters_for_month(snapshot.year, month)
    expected = page_count(api.get_payments_page(filters))
    payload = api.get_payments_export(filters)
    if not isinstance(payload, list) or len(payload) != expected:
        raise ValueError('A exportação diverge da quantidade esperada.')

    records, seen = [], set()
    total = Decimal('0.00')
    for item in payload:
        data = normalize(item, snapshot.year, month)
        key = (data['unit_code'], data['number'])
        if key in seen:
            raise ValueError('Documento repetido na exportação mensal.')
        seen.add(key)
        total += data['amount']
        records.append(Payment(snapshot=snapshot, **data))

    Payment.objects.bulk_create(records, batch_size=BATCH_SIZE)
    return len(records), total


def publish(snapshot, count, total):
    with transaction.atomic():
        previous = PaymentSnapshot.objects.filter(year=snapshot.year, status=STATUS.PUBLISHED).first()
        if previous:
            previous.status = STATUS.REPLACED
            previous.save(update_fields=('status',))
        snapshot.status = STATUS.PUBLISHED
        snapshot.record_count = count
        snapshot.total = total
        snapshot.finished_at = timezone.now()
        snapshot.save(update_fields=('status', 'record_count', 'total', 'finished_at'))
        # Uma página que acabou de selecionar o conjunto anterior ainda pode lê-lo.
        old = PaymentSnapshot.objects.filter(year=snapshot.year, status=STATUS.REPLACED)
        if previous:
            old = old.exclude(pk=previous.pk)
        Payment.objects.filter(snapshot__in=old).delete()


def sync_payments(*, year=None, month_end=None, client=None, today=None):
    today = today or datetime.now(LOCAL_TIME_ZONE).date()
    year = year if year is not None else today.year
    if not 2000 <= year <= today.year:
        raise PaymentSyncError('Escolha um ano entre 2000 e o ano atual.')
    latest_month = today.month if year == today.year else 12
    month_end = month_end if month_end is not None else latest_month
    if not 1 <= month_end <= latest_month:
        raise PaymentSyncError('Escolha um mês dentro do período disponível.')

    with year_lock(year):
        if PaymentSnapshot.objects.filter(
            year=year, status=STATUS.PUBLISHED, month_end__gt=month_end,
        ).exists():
            raise PaymentSyncError('A coleta solicitada cobre menos meses que o conjunto publicado.')
        if connection.vendor == 'postgresql':
            # Com o lock adquirido, uma coleta ainda pendente foi interrompida.
            abandoned = PaymentSnapshot.objects.filter(year=year, status=STATUS.LOADING)
            Payment.objects.filter(snapshot__in=abandoned).delete()
            abandoned.update(status=STATUS.FAILED, failure_stage='interrompida', finished_at=timezone.now())

        snapshot = PaymentSnapshot.objects.create(year=year, month_end=month_end)
        stage = 'conexão'
        count, total = 0, Decimal('0.00')
        try:
            with (nullcontext(client) if client is not None else FiplanClient()) as api:
                for month in range(1, month_end + 1):
                    stage = f'mês {month:02d}'
                    month_count, month_total = collect_month(api, snapshot, month)
                    count += month_count
                    total += month_total
            stage = 'publicação'
            publish(snapshot, count, total)
        except Exception as exc:
            snapshot.payments.all().delete()
            PaymentSnapshot.objects.filter(pk=snapshot.pk).update(
                status=STATUS.FAILED, record_count=count, finished_at=timezone.now(),
                failure_stage=stage, failure_type=type(exc).__name__,
            )
            raise PaymentSyncError(f'Coleta interrompida em {stage} ({type(exc).__name__}).') from None
    return snapshot


def describe_payments(snapshot):
    return (
        f'Pagamentos atualizados: {snapshot.record_count} registros, '
        f'01–{snapshot.month_end:02d}/{snapshot.year}.'
    )
