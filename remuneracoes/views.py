from decimal import Decimal
from urllib.parse import urlencode

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from portal.errors import PUBLIC_ERRORS
from portal.formatting import MONTHS, brl, local_datetime
from portal.glossary import terms

from .mappers import MINIMUM_WAGES, present_row
from .models import PayrollSnapshot
from .services import recent_periods

# Campos do detalhamento com rótulos em linguagem simples (termo oficial entre parênteses).
STATEMENT_LABELS = (
    ('base', 'Salário-base (vencimento)'),
    ('other', 'Adicionais e gratificações'),
    ('mandatory', 'Descontos obrigatórios: impostos e previdência'),
    ('authorized', 'Descontos autorizados, como empréstimos'),
    ('gross', 'Total antes dos descontos (bruto)'),
    ('net', 'Valor recebido (líquido)'),
)
EVENT_KINDS = {'P': 'Acréscimo', 'D': 'Desconto'}


def snapshot_context(snapshot):
    wage = MINIMUM_WAGES.get(snapshot.year) if snapshot else None
    return {
        'snapshot': snapshot,
        'period_label': f'{MONTHS[snapshot.month - 1]} de {snapshot.year}' if snapshot else '',
        'updated_at': local_datetime(snapshot.updated_at) if snapshot else '',
        'wage': {**wage, 'formatted': brl(wage['amount'])} if wage else None,
        'glossary': terms('bruto', 'liquido', 'matricula'),
    }


def index(request):
    periods = list(PayrollSnapshot.objects.values_list('year', 'month'))
    default_year, default_month = periods[0] if periods else next(recent_periods())
    error = ''
    try:
        year = int(request.GET.get('ano', default_year))
        month = int(request.GET.get('mes', default_month))
        if not 2000 <= year <= 9999 or not 1 <= month <= 12:
            raise ValueError
    except (ValueError, TypeError):
        year, month = default_year, default_month
        error = PUBLIC_ERRORS['ENTRADA-001']['message']
    snapshot = PayrollSnapshot.objects.filter(year=year, month=month).first() if not error else None
    agency = request.GET.get('orgao', '').strip()
    multiple = request.GET.get('multiplas') == '1'
    rows = snapshot.rows if snapshot else []
    agencies = sorted({row['agency'] for row in rows})
    filtered = [present_row(row, year) for row in rows
                if (not agency or row['agency'] == agency)
                and (not multiple or row['membership_count'] > 1)]
    return render(request, 'remuneracoes/index.html', {
        **snapshot_context(snapshot),
        'rows': filtered, 'total_count': len(rows), 'agencies': agencies,
        'years': sorted({p[0] for p in periods} | {year}, reverse=True),
        'months': list(enumerate(MONTHS, 1)), 'year': year, 'month': month,
        'agency': agency, 'multiple': multiple, 'error': error,
        'error_code': 'ENTRADA-001' if error else '',
        'status': 'Último período disponível' if periods and (year, month) == periods[0] else '',
        'query_string': urlencode({'ano': year, 'mes': month, 'orgao': agency, **({'multiplas': '1'} if multiple else {})}),
        'result_count_label': f'{len(filtered)} de {len(rows)} registros',
        'reset_url': reverse('remuneracoes:index') + '?' + urlencode({'ano': year, 'mes': month}),
        'empty_period_description': f'Não há dados importados para {month:02d}/{year}. Isso não significa que não houve pagamentos. Consulte o último período disponível ou aguarde a próxima atualização.',
    })


def detail(request, year, month, record_id):
    snapshot = get_object_or_404(PayrollSnapshot, year=year, month=month)
    row = next((row for row in snapshot.rows if row['id'] == str(record_id)), None)
    if row is None:
        raise Http404('Registro não encontrado neste período.')
    statements = [{
        **statement,
        'amounts': [(label, brl(statement[key])) for key, label in STATEMENT_LABELS],
        'events': [{**event, 'formatted': brl(event['amount']),
                    'kind_label': EVENT_KINDS.get(event['kind'], event['kind'] or 'Tipo não informado')}
                   for event in statement['events']],
    } for statement in row['statements']]
    gross_values = [statement['gross'] for statement in row['statements']]
    comparable = bool(gross_values) and all(value is not None for value in gross_values)
    mismatch = comparable and sum((Decimal(value) for value in gross_values), Decimal('0')) != Decimal(row['amount'])
    back_params = {'ano': year, 'mes': month}
    if request.GET.get('orgao'):
        back_params['orgao'] = request.GET['orgao']
    if request.GET.get('multiplas') == '1':
        back_params['multiplas'] = '1'
    return render(request, 'remuneracoes/detail.html', {
        **snapshot_context(snapshot), 'row': present_row(row, year),
        'statements': statements, 'mismatch': mismatch,
        'back_url': reverse('remuneracoes:index') + '?' + urlencode(back_params),
    })
