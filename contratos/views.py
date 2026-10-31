import unicodedata
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

from django.db.models import Sum
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from portal.formatting import br_date, local_datetime
from portal.glossary import terms

from .mappers import extended
from .models import Contract, ContractDetail, ContractSnapshot
from .services import local_today

LIST_LIMIT = 50
HIGHLIGHTED_AGENCIES = 6
EXPIRING_DAYS = 90
EXPIRING_HIGHLIGHTS = 6
DEFAULT_SORT = 'valor'
FILTER_PARAMS = ('busca', 'orgao', 'ordem')
RECEITA_CNPJ_URL = 'https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp?cnpj={}'
SORTS = {
    'valor': 'Maior valor em contratos',
    'orgaos': 'Atende mais órgãos',
    'contratos': 'Mais contratos',
}


def _folded(value):
    decomposed = unicodedata.normalize('NFKD', value.casefold())
    return ''.join(char for char in decomposed if not unicodedata.combining(char))


def _percent_label(value):
    # Percentuais do snapshot têm uma casa decimal: "70.0" vira "70%", "6.3" vira "6,3%".
    value = str(value)
    return (value[:-2] if value.endswith('.0') else value).replace('.', ',') + '%'


def _count_label(count, singular, plural):
    return f'{count} {singular if count == 1 else plural}'


def _with_query(url, params, fragment=''):
    return url + (f'?{urlencode(params)}' if params else '') + fragment


def _snapshot_context(snapshot):
    return {
        'snapshot': snapshot, 'year': snapshot.fiscal_year,
        'period_label': f'Contratos com vigência em {snapshot.fiscal_year}',
        'updated_at': local_datetime(snapshot.updated_at),
    }


def _expiring(year, today, agency_code=''):
    contracts = Contract.objects.filter(
        fiscal_year=year, situation='Ativo', end__gte=today, end__lte=today + timedelta(days=EXPIRING_DAYS),
    )
    return contracts.filter(agency_code=agency_code) if agency_code else contracts


def _days_left_label(end, today):
    days = (end - today).days
    return {0: 'Vence hoje', 1: 'Vence amanhã'}.get(days, f'Vence em {days} dias')


def _present_expiring(contract, today):
    return {
        'contract': contract, 'end_label': br_date(contract.end),
        'days_left_label': _days_left_label(contract.end, today),
    }


def _sort_key(order):
    if order == 'orgaos':
        return lambda row: (-row['agency_count'], -Decimal(row['scope']['contracted']), row['name'])
    if order == 'contratos':
        return lambda row: (-row['scope']['contracts'], -Decimal(row['scope']['contracted']), row['name'])
    return lambda row: (-Decimal(row['scope']['contracted']), row['name'])


def _with_percent_label(row):
    return {**row, 'percent_label': _percent_label(row['percent'])} if row else None


def _present_agency(agency):
    return {
        **agency,
        'top': [_with_percent_label(row) for row in agency['top']],
        'others': _with_percent_label(agency['others']),
    }


def _present_supplier(row, agency_code=''):
    scope = next((link for link in row['agencies'] if link['code'] == agency_code), None) if agency_code else None
    return {
        **row,
        'document_label': f'CNPJ {row["document"]}' if row['cnpj'] else f'Pessoa física · CPF {row["document"]}',
        'scope': scope or {'contracted': row['contracted'], 'contracts': row['contracts']},
        'scope_percent_label': _percent_label(scope['percent']) if scope else '',
        'agency_names': [link['name'] for link in row['agencies'][:3]],
        'more_agencies': max(row['agency_count'] - 3, 0),
        'dominant_label': _percent_label(row['dominant']['percent']) if row['dominant'] else '',
        'receita_url': RECEITA_CNPJ_URL.format(row['cnpj']) if row['cnpj'] else '',
        'paid_exceeds': Decimal(row['paid']) > Decimal(row['contracted']),
    }


def _filter_suppliers(rows, agency_code, query):
    if agency_code:
        rows = [row for row in rows if any(link['code'] == agency_code for link in row['agencies'])]
    if query:
        folded, digits = _folded(query), ''.join(char for char in query if char.isdigit())
        rows = [row for row in rows
                if folded in _folded(row['name']) or (len(digits) >= 4 and digits in row['cnpj'])]
    return rows


def index(request):
    snapshot = ContractSnapshot.objects.first()
    context = {'glossary': terms('contrato', 'vigencia', 'aditivo', 'liquidacao', 'pagamento', 'credor')}
    if not snapshot:
        return render(request, 'contratos/index.html', context)

    agencies = snapshot.agencies
    agency_code = request.GET.get('orgao', '').strip()
    if agency_code not in {agency['code'] for agency in agencies}:
        agency_code = ''
    order = request.GET.get('ordem', DEFAULT_SORT)
    if order not in SORTS:
        order = DEFAULT_SORT
    query = request.GET.get('busca', '').strip()[:80]

    rows = sorted(
        (_present_supplier(row, agency_code) for row in _filter_suppliers(snapshot.suppliers, agency_code, query)),
        key=_sort_key(order),
    )
    for position, row in enumerate(rows, 1):
        row['position'] = position
    filters = {'busca': query, 'orgao': agency_code, 'ordem': order if order != DEFAULT_SORT else ''}
    filters = {key: value for key, value in filters.items() if value}

    highlighted = [agency for agency in agencies if agency['code'] == agency_code] or agencies[:HIGHLIGHTED_AGENCIES]
    summary = snapshot.summary
    contracted = Decimal(summary['contracted'])
    history = snapshot.history
    largest_paid = max((Decimal(row['paid']) for row in history), default=Decimal('0'))
    today = local_today()
    expiring = _expiring(snapshot.fiscal_year, today, agency_code)
    expiring_count = expiring.count()
    context.update({
        **_snapshot_context(snapshot), 'summary': summary,
        'query_string': urlencode(filters),
        'expiring_count': expiring_count,
        'expiring_count_label': _count_label(expiring_count, 'contrato', 'contratos'),
        'expiring_total': expiring.aggregate(total=Sum('contracted'))['total'],
        'expiring_url': _with_query(reverse('contratos:expiring'), {'orgao': agency_code} if agency_code else {}),
        'expiring': [_present_expiring(contract, today)
                     for contract in expiring.order_by('-contracted', 'contract_id')[:EXPIRING_HIGHLIGHTS]],
        'agency_options': sorted(agencies, key=lambda agency: agency['name']),
        'selected_agency': highlighted[0] if agency_code else None,
        'highlighted_agencies': [_present_agency(agency) for agency in highlighted],
        'rows': rows[:LIST_LIMIT],
        'result_count_label': f'{min(len(rows), LIST_LIMIT)} de {_count_label(len(rows), "fornecedor", "fornecedores")}',
        'sorts': SORTS.items(), 'order': order, 'agency_code': agency_code, 'query': query,
        'filtered': bool(agency_code or query),
        'reset_url': reverse('contratos:index'),
        'history': [{
            **row,
            'bar_percent': str((Decimal(row['paid']) / largest_paid * 100).quantize(Decimal('0.1'))) if largest_paid > 0 else '0',
        } for row in history],
        'paid_percent': _percent_label(
            (Decimal(summary['paid']) / contracted * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        ) if contracted > 0 else '',
    })
    return render(request, 'contratos/index.html', context)


def _growth_label(contract):
    if not contract.original or contract.original <= 0:
        return ''
    ratio = contract.contracted / contract.original
    if ratio >= 2:
        return f'{ratio:.1f}'.replace('.', ',') + '× o valor assinado'
    increase = ((ratio - 1) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    # Diferenças de centavos arredondam para 0% e não merecem destaque.
    return f'+{increase}% sobre o valor assinado' if increase > 0 else ''


def _present_contract(contract, detail):
    paid_share = contract.paid / contract.contracted * 100 if contract.contracted > 0 else Decimal('0')
    return {
        'contract': contract, 'growth': _growth_label(contract),
        'paid_bar': str(min(max(paid_share, Decimal('0')), Decimal('100')).quantize(Decimal('0.1'))),
        'paid_label': f'{paid_share.quantize(Decimal("1"), rounding=ROUND_HALF_UP)}%',
        'paid_exceeds': contract.paid > contract.contracted,
        'start_label': br_date(contract.start), 'end_label': br_date(contract.end),
        'original_end_label': br_date(contract.original_end) if extended(contract.end, contract.original_end) else '',
        'collected': detail is not None,
        'inspectors': detail.inspectors if detail else [],
        'additives': [{
            **additive, 'date_label': br_date(additive['date']),
            'period_label': f'{br_date(additive["start"])} a {br_date(additive["end"])}' if additive['end'] else '',
        } for additive in (detail.additives if detail else [])],
    }


def supplier(request, supplier_id):
    snapshot = ContractSnapshot.objects.first()
    row = next((row for row in snapshot.suppliers if row['id'] == supplier_id), None) if snapshot else None
    if row is None:
        raise Http404('Fornecedor não encontrado nos contratos deste ano.')
    contracts = list(Contract.objects.filter(fiscal_year=snapshot.fiscal_year, supplier_id=supplier_id)
                     .order_by('-contracted', 'contract_id'))
    details = ContractDetail.objects.in_bulk([contract.contract_id for contract in contracts])
    presented = [_present_contract(contract, details.get(contract.contract_id)) for contract in contracts]
    back_params = {key: request.GET[key] for key in FILTER_PARAMS if request.GET.get(key)}
    return render(request, 'contratos/supplier.html', {
        **_snapshot_context(snapshot),
        'row': _present_supplier(row),
        'agencies': [_with_percent_label(link) for link in row['agencies']],
        'contracts': presented,
        'collected_count': sum(1 for contract in presented if contract['collected']),
        'additive_count': sum(len(contract['additives']) for contract in presented),
        'back_url': _with_query(reverse('contratos:index'), back_params, '#fornecedores'),
        'glossary': terms('contrato', 'vigencia', 'aditivo', 'fiscal', 'processo_sei', 'pagamento'),
    })


def expiring(request):
    snapshot = ContractSnapshot.objects.first()
    today = local_today()
    context = {
        'rows': [], 'agency': None, 'updated_at': '',
        'period_label': f'Próximos {EXPIRING_DAYS} dias a partir de {br_date(today)}',
        'back_url': reverse('contratos:index'),
        'glossary': terms('vigencia', 'aditivo', 'processo_sei'),
    }
    if snapshot:
        agency = next((agency for agency in snapshot.agencies if agency['code'] == request.GET.get('orgao')), None)
        contracts = _expiring(snapshot.fiscal_year, today, agency['code'] if agency else '').order_by('end', '-contracted')
        context.update({
            'agency': agency, 'updated_at': local_datetime(snapshot.updated_at),
            'rows': [_present_expiring(contract, today) for contract in contracts],
        })
    context['count_label'] = _count_label(len(context['rows']), 'contrato', 'contratos')
    return render(request, 'contratos/expiring.html', context)
