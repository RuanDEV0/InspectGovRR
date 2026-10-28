from decimal import Decimal, ROUND_HALF_UP

from django.shortcuts import render

from portal.formatting import local_datetime, month_range
from portal.glossary import terms
from unidades.models import Unit

from .models import RevenueSnapshot
from .services import current_period


def _explanation(acronym, name):
    if 'DETRAN' in f'{acronym} {name}'.upper():
        return 'Pode incluir taxas de licenciamento, multas e serviços de habilitação.'
    if 'TESOURO' in name.upper():
        return 'É o caixa central do governo: recebe a maior parte dos impostos, como ICMS e IPVA, e repasses federais.'
    return (
        'Órgãos e fundos podem receber tributos, taxas, repasses, convênios ou rendimentos, '
        'conforme suas atribuições. Este ranking não detalha a origem de cada valor.'
    )


def index(request):
    snapshot = RevenueSnapshot.objects.first()
    context = {'glossary': terms('receita', 'tesouro', 'unidade', 'fundo'), 'rows': []}
    if not snapshot:
        return render(request, 'receita_arrecadada/index.html', context)

    codes = [row['unit_code'] for row in snapshot.rows]
    acronyms = dict(Unit.objects.filter(code__in=codes).values_list('code', 'acronym'))
    amounts = [Decimal(row['amount']) for row in snapshot.rows]
    maximum = max((amount for amount in amounts if amount > 0), default=Decimal('0'))
    rows = []
    for position, (row, amount) in enumerate(zip(snapshot.rows, amounts), start=1):
        acronym = (acronyms.get(row['unit_code']) or '').strip(' ,') or row['unit_name']
        rows.append({
            **row,
            'position': position,
            'acronym': acronym,
            'bar_percent': str((max(amount, 0) / maximum * 100).quantize(Decimal('0.1'))) if maximum else '0',
            'explanation': _explanation(acronym, row['unit_name']),
        })

    positive_total = sum((amount for amount in amounts if amount > 0), Decimal('0'))
    if rows and positive_total:
        share = (amounts[0] / positive_total * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        context['citizen_insight'] = {'unit_name': rows[0]['unit_name'], 'per_hundred': int(share)}

    year, _, month = current_period()
    context.update({
        'rows': rows,
        'podium': rows[:3],
        'period_label': month_range(snapshot.fiscal_year, snapshot.month_start, snapshot.month_end),
        'updated_at': local_datetime(snapshot.updated_at),
        'status': '' if (snapshot.fiscal_year, snapshot.month_end) == (year, month) else 'Último período disponível',
    })
    return render(request, 'receita_arrecadada/index.html', context)
