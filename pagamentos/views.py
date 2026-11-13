from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from portal.errors import PUBLIC_ERRORS
from portal.formatting import LOCAL_TIME_ZONE, MONTHS, local_datetime, month_range
from portal.glossary import terms

from .areas import AREAS, AREA_YEAR, NATURE_LABELS
from .models import PaymentSnapshot

GLOSSARY = ('pagamento', 'unidade', 'natureza', 'credor')
ALL_UNITS = tuple(code for _, codes in AREAS.values() for code in codes)
OTHER = 'outros'
EVERYTHING = 'todos'
SCOPE_TITLES = {OTHER: 'Outros órgãos', EVERYTHING: 'Todos os órgãos'}
UNCLASSIFIED = 'sem-classificacao'
RECENT = 'recentes'
PAGE_SIZE = 15
SPLIT_SLICES = 5
TOP_PAYMENTS = 10
TOP_RECIPIENTS = 8
PANEL_RECIPIENTS = 3
CACHE_SECONDS = 3600
CENT = Decimal('0.01')
# Valor de descTipoDespesa que a fonte usa nos registros de folha.
PAYROLL = 'Folha de Pagamento'
# Modalidade 91 (3º e 4º dígitos da natureza): operação entre órgãos do próprio orçamento.
INTERNAL = Q(nature_code__regex=r'^[0-9]{2}91')


def choices_url(params, **changes):
    query = {**params, **changes}
    return '?' + urlencode({key: value for key, value in query.items() if value not in (None, '')})


def bar_width(value, peak):
    return f'{max(value, 0) / peak * 100:.1f}' if peak > 0 else '0'


def per_hundred(value, total):
    """Quanto de cada R$ 100 do total corresponde ao valor. Só vale para somas positivas."""
    if value is None or not total or total <= 0 or value < 0:
        return None
    return (value / total * 100).quantize(CENT, rounding=ROUND_HALF_UP)


def branch_rows(rows, params, filter_name, current):
    peak = max((row['total'] for row in rows), default=Decimal(0))
    target = '#registros' if filter_name == 'despesa' else '#painel'
    return [
        {
            **row,
            'active': row['key'] == current,
            'width': bar_width(row['total'], peak),
            'url': choices_url(params, **{filter_name: row['key']}) + target,
        }
        for row in rows
    ]


def split_slices(rows, total):
    """Reparte R$ 100 pelos maiores tipos de despesa. Só vale quando nenhuma soma é negativa."""
    if not total or total <= 0 or any(row['total'] < 0 for row in rows):
        return []
    slices = [{**row, 'share': per_hundred(row['total'], total)} for row in rows[:SPLIT_SLICES]]
    if len(rows) > SPLIT_SLICES:
        rest = max(Decimal(100) - sum(item['share'] for item in slices), Decimal(0))
        slices.append({'label': 'Demais tipos de despesa', 'share': rest, 'url': '#detalhar',
                       'count': len(rows) - SPLIT_SLICES})
    return slices


def nature_branches(query, params, current=''):
    rows = query.values('nature_code').annotate(name=Max('nature_name'), total=Sum('amount')) \
        .order_by('-total', 'nature_code')
    return branch_rows([
        {'key': row['nature_code'] or UNCLASSIFIED, 'label': label_nature(row['nature_code'], row['name']),
         'code': row['nature_code'],
         'official': row['name'] if row['nature_code'] in NATURE_LABELS else '', 'total': row['total']}
        for row in rows
    ], params, 'despesa', current)


def month_bars(query, first, last):
    sums = dict(query.values_list('paid_on__month').annotate(total=Sum('amount')))
    peak = max(sums.values(), default=Decimal(0))
    return [
        {'name': MONTHS[n - 1], 'short': MONTHS[n - 1][:3], 'total': sums.get(n, Decimal(0)),
         'width': bar_width(sums.get(n, Decimal(0)), peak), 'peak': peak > 0 and sums.get(n) == peak}
        for n in range(first, last + 1)
    ]


def build_insight(query, params, period, state_total=None, recipients=TOP_RECIPIENTS, top=TOP_PAYMENTS):
    """Resumo de um conjunto de pagamentos. Todos os números são cálculos do portal."""
    sums = query.aggregate(
        total=Sum('amount'), count=Count('pk'),
        payroll=Sum('amount', filter=Q(expense_type=PAYROLL)), internal=Sum('amount', filter=INTERNAL),
    )
    if not sums['count']:
        return None
    total = sums['total']
    who = query.filter(creditor_kind='company').exclude(expense_type=PAYROLL).exclude(creditor_name='') \
        .values('creditor_name').annotate(total=Sum('amount'), count=Count('pk')) \
        .order_by('-total', 'creditor_name')[:recipients]
    who = list(who)
    most = who[0]['total'] if who else Decimal(0)
    months = month_bars(query, 1, period['last_month']) if period['month'] is None else []
    return {
        'total': total,
        'count': sums['count'],
        'days': period['days'],
        'per_day': (total / period['days']).quantize(CENT, rounding=ROUND_HALF_UP),
        'of_state': per_hundred(total, state_total),
        'payroll': sums['payroll'],
        'payroll_share': per_hundred(sums['payroll'], total),
        'internal': sums['internal'],
        'months': months,
        'peak_month': next((row for row in months if row['peak']), None),
        'recipients': [
            {**row, 'width': bar_width(row['total'], most),
             'url': choices_url(params, credor=row['creditor_name']) + '#registros'} for row in who
        ],
        'top': list(query.order_by('-amount', '-id')[:top]),
        'top_outside': query.exclude(expense_type=PAYROLL).order_by('-amount', '-id').first(),
    }


def year_filter(value):
    if len(value) != 4 or not value.isascii() or not value.isdecimal():
        return None
    year = int(value)
    return year if 2000 <= year <= 9999 else None


def short_filter(value):
    return bool(value) and len(value) <= 20 and value.isascii() and value.isdecimal()


def apply_area(query, area):
    if area == OTHER:
        return query.exclude(unit_code__in=ALL_UNITS)
    if area in AREAS:
        return query.filter(unit_code__in=AREAS[area][1])
    return query


def label_nature(code, name):
    return NATURE_LABELS.get(code, name or (f'Natureza {code}' if code else 'Tipo de despesa não informado'))


def index(request):
    snapshots = PaymentSnapshot.objects.filter(status=PaymentSnapshot.Status.PUBLISHED)
    years = list(snapshots.values_list('year', flat=True))
    year = year_filter(request.GET['ano']) if 'ano' in request.GET else next(iter(years), None)
    context = {
        'years': years, 'year': year, 'glossary': terms(*GLOSSARY),
        'no_snapshot_message': PUBLIC_ERRORS['DADOS-001']['message'],
    }
    if 'ano' in request.GET and year is None:
        return invalid_filter(request, context)

    snapshot = snapshots.filter(year=year).first() if year else None
    if snapshot is None:
        return render(request, 'pagamentos/index.html', context)

    area, unit, nature, creditor, raw_month, order = (
        request.GET.get(key, '') for key in ('area', 'orgao', 'despesa', 'credor', 'mes', 'ordem')
    )
    has_areas = year == AREA_YEAR
    if (
        (area and area != EVERYTHING and (not has_areas or area not in (*AREAS, OTHER)))
        or (unit and not short_filter(unit))
        or (nature and nature != UNCLASSIFIED and not short_filter(nature))
        or (raw_month and (not short_filter(raw_month) or not 1 <= int(raw_month) <= snapshot.month_end))
        or len(creditor) > 255
        or order not in ('', RECENT)
    ):
        return invalid_filter(request, context)

    month = int(raw_month) if raw_month else None
    params = {'ano': year, 'mes': month}
    period_query = snapshot.payments.all()
    if month:
        start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
        period_query = period_query.filter(paid_on__range=(start, end))

    # A lista de órgãos vem do período coletado. A soma da lista respeita o mês escolhido.
    all_units = dict(snapshot.payments.values('unit_code').annotate(name=Max('unit_name'))
                     .values_list('unit_code', 'name'))
    if unit and (
        unit not in all_units
        or (area == OTHER and unit in ALL_UNITS)
        or (area in AREAS and unit not in AREAS[area][1])
    ):
        return invalid_filter(request, context)

    collected = timezone.localtime(snapshot.finished_at, LOCAL_TIME_ZONE)
    last_month = month or snapshot.month_end
    partial_month = (collected.year, collected.month) == (year, last_month)
    last_day = collected.date() if partial_month else date(year, last_month, monthrange(year, last_month)[1])
    period = {'month': month, 'last_month': last_month, 'days': (last_day - date(year, month or 1, 1)).days + 1}
    # Um conjunto publicado não muda: os resumos podem ser guardados até a próxima coleta.
    cache_key = f'pagamentos:{snapshot.pk}:{snapshot.finished_at.timestamp()}:{month}'
    failed_update = PaymentSnapshot.objects.filter(
        year=year, id__gt=snapshot.pk, status=PaymentSnapshot.Status.FAILED, month_end__gte=snapshot.month_end,
    ).exists()
    context.update({
        'snapshot': snapshot,
        'period': month_range(year, month or 1, last_month),
        'updated_at': local_datetime(snapshot.finished_at),
        'partial_month': partial_month,
        'failed_update': failed_update,
        'refresh_warning': PUBLIC_ERRORS['DADOS-003']['message'],
        'empty_message': PUBLIC_ERRORS['DADOS-002']['message'],
        'months': [(n, name) for n, name in enumerate(MONTHS[:snapshot.month_end], 1)],
        'month': month, 'area': area, 'unit': unit, 'nature': nature, 'creditor': creditor, 'order': order,
        'home_url': choices_url(params) + '#resumo',
        'explore_url': choices_url(params, area=EVERYTHING) + '#painel',
        'other_url': choices_url(params, area=OTHER) + '#painel' if has_areas else '',
    })

    if not (area or unit or nature or creditor):
        context.update(cache.get_or_set(
            cache_key, lambda: landing(period_query, params, period, all_units, has_areas), CACHE_SECONDS,
        ))
        return render(request, 'pagamentos/index.html', context)

    scope_params = {**params, 'area': area, 'orgao': unit}
    area_query = apply_area(period_query, area)
    unit_query = area_query.filter(unit_code=unit) if unit else area_query
    unit_rows = list(area_query.values('unit_code').annotate(name=Max('unit_name'), total=Sum('amount'))
                     .order_by('-total', 'unit_code'))
    natures = nature_branches(unit_query, scope_params, nature)
    visible = unit_query
    if nature:
        visible = visible.filter(nature_code='' if nature == UNCLASSIFIED else nature)
    if creditor:
        visible = visible.filter(creditor_kind='company', creditor_name=creditor)

    # O painel resume a área ou o órgão. Com despesa ou recebedor escolhido, a página vai direto aos registros.
    insight = None
    if not (nature or creditor):
        def scope_insight():
            # A parte do estado só faz sentido quando o painel não é o próprio estado inteiro.
            state_total = period_query.aggregate(total=Sum('amount'))['total'] if unit or area != EVERYTHING else None
            data = build_insight(unit_query, scope_params, period, state_total)
            if data:
                data['slices'] = split_slices(natures, data['total'])
            return data
        insight = cache.get_or_set(f'{cache_key}:{area}:{unit}', scope_insight, CACHE_SECONDS)

    totals = visible.aggregate(total=Sum('amount'), count=Count('pk'))
    ordering = ('-paid_on', '-id') if order == RECENT else ('-amount', '-id')
    page = Paginator(visible.order_by(*ordering), PAGE_SIZE).get_page(request.GET.get('pagina'))
    filters = {**scope_params, 'despesa': nature, 'credor': creditor}
    listing = {**filters, 'ordem': order}
    area_title = AREAS[area][0] if area in AREAS else SCOPE_TITLES.get(area, '')
    unit_name = all_units.get(unit, '')
    context.update({
        'insight': insight,
        'scope_title': unit_name or area_title or 'Todos os órgãos',
        'area_title': area_title,
        'area_units': sorted(all_units.get(code, name) for code, name in AREAS[area][1].items())
        if area in AREAS else [],
        'unit_name': unit_name,
        'area_url': choices_url(params, area=area) + '#painel',
        'unit_url': choices_url(scope_params) + '#painel',
        'unit_rows': branch_rows([
            {'key': row['unit_code'], 'label': row['name'], 'total': row['total']} for row in unit_rows
        ], {**params, 'area': area}, 'orgao', unit),
        'nature_rows': natures,
        'nature_label': next((row['label'] for row in natures if row['key'] == nature), ''),
        'total': totals['total'],
        'record_count': totals['count'],
        'page': page,
        'by_value_url': choices_url(filters) + '#registros',
        'by_date_url': choices_url(filters, ordem=RECENT) + '#registros',
        'previous_url': choices_url(listing, pagina=page.previous_page_number()) + '#registros'
        if page.has_previous() else '',
        'next_url': choices_url(listing, pagina=page.next_page_number()) + '#registros' if page.has_next() else '',
    })
    return render(request, 'pagamentos/index.html', context)


def landing(period_query, params, period, all_units, has_areas):
    """Abertura: o resumo do estado e, quando há regra de áreas para o ano, um painel por área."""
    insight = build_insight(period_query, {**params, 'area': EVERYTHING}, period)
    panels = []
    if insight:
        natures = nature_branches(period_query, {**params, 'area': EVERYTHING})
        insight['slices'] = split_slices(natures, insight['total'])
    if insight and has_areas:
        for key, (title, units) in AREAS.items():
            area_params = {**params, 'area': key}
            data = build_insight(
                period_query.filter(unit_code__in=units), area_params, period, insight['total'],
                recipients=PANEL_RECIPIENTS, top=1,
            )
            panels.append({
                'key': key, 'title': title, 'insight': data,
                'url': choices_url(area_params) + '#painel',
                'unit_names': sorted(all_units.get(code, name) for code, name in units.items()),
            })
    return {'landing': True, 'insight': insight, 'panels': panels}


def invalid_filter(request, context):
    context['filter_error'] = PUBLIC_ERRORS['PAGAMENTOS-FILTRO']['message']
    return render(request, 'pagamentos/index.html', context, status=400)
