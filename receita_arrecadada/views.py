from decimal import Decimal, ROUND_HALF_UP

from django.shortcuts import render
from django.utils import timezone

from unidades.models import Unit

from .models import RevenueSnapshot
from .services import RORAIMA_TIME_ZONE, current_period

MONTHS = (
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
)


def _full_currency(value):
    formatted = f'{value:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return f'R$ {formatted}'


def _explanation(acronym, name):
    if 'DETRAN' in f'{acronym} {name}'.upper():
        return 'Pode incluir taxas de licenciamento, multas e serviços de habilitação.'
    return (
        'Órgãos e fundos podem registrar tributos, taxas, transferências, convênios '
        'ou rendimentos conforme suas atribuições. Este ranking não detalha a origem de cada valor.'
    )


def index(request):
    snapshot = RevenueSnapshot.objects.first()
    rows = []
    period_label = None
    updated_at = None
    is_current_period = False
    citizen_insight = None

    if snapshot:
        codes = [row['unit_code'] for row in snapshot.rows]
        acronyms = dict(Unit.objects.filter(code__in=codes).values_list('code', 'acronym'))
        amounts = [Decimal(row['amount']) for row in snapshot.rows]
        maximum = max((amount for amount in amounts if amount > 0), default=Decimal('0'))
        for position, (row, amount) in enumerate(zip(snapshot.rows, amounts), start=1):
            acronym = acronyms.get(row['unit_code']) or row['unit_code']
            rows.append({
                **row,
                'position': position,
                'acronym': acronym,
                'full_amount': _full_currency(amount),
                'bar_percent': str((max(amount, 0) / maximum * 100).quantize(Decimal('0.1'))) if maximum else '0',
                'explanation': _explanation(acronym, row['unit_name']),
            })
        positive_total = sum((amount for amount in amounts if amount > 0), Decimal('0'))
        if rows and positive_total:
            share = (amounts[0] / positive_total * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            citizen_insight = {
                'unit_name': rows[0]['unit_name'],
                'per_hundred': int(share),
            }
        start = MONTHS[snapshot.month_start - 1]
        end = MONTHS[snapshot.month_end - 1]
        period_label = (
            f'{start} de {snapshot.fiscal_year}' if snapshot.month_start == snapshot.month_end
            else f'{start} a {end} de {snapshot.fiscal_year}'
        )
        updated_at = timezone.localtime(snapshot.updated_at, RORAIMA_TIME_ZONE).strftime('%d/%m/%Y às %H:%M')
        year, _, month = current_period()
        is_current_period = snapshot.fiscal_year == year and snapshot.month_end == month

    return render(request, 'receita_arrecadada/index.html', {
        'rows': rows,
        'podium': rows[:3],
        'period_label': period_label,
        'updated_at': updated_at,
        'is_current_period': is_current_period,
        'citizen_insight': citizen_insight,
    })
