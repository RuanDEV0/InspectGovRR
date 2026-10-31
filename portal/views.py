from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse

from contratos.models import ContractSnapshot
from receita_arrecadada.models import RevenueSnapshot
from remuneracoes.mappers import present_row
from remuneracoes.models import PayrollSnapshot
from unidades.models import Unit

from .errors import PUBLIC_ERRORS
from .formatting import MONTHS, brl_compact, month_range
from .glossary import MONEY_PATH, TERMS, terms
from .modules import UPCOMING, UPCOMING_COUNT


def _highlights():
    """Destaques de registros importados com comparação externa identificada no módulo."""
    items = []
    revenue = RevenueSnapshot.objects.first()
    if revenue and revenue.rows:
        top = revenue.rows[0]
        items.append({
            'icon': 'arrecadacao', 'url_name': 'receita_arrecadada:index',
            'label': f'Maior arrecadação · {month_range(revenue.fiscal_year, revenue.month_start, revenue.month_end)}',
            'value': brl_compact(top['amount']), 'caption': top['unit_name'],
        })
    payroll = PayrollSnapshot.objects.first()
    if payroll and payroll.rows:
        top = present_row(payroll.rows[0], payroll.year)
        caption = f'≈ {top["equivalent"]} salários mínimos em um mês' if top['equivalent'] else top['agency']
        items.append({
            'icon': 'salarios', 'url_name': 'remuneracoes:index',
            'label': f'Maior salário bruto · {MONTHS[payroll.month - 1]} de {payroll.year}',
            'value': brl_compact(top['amount']), 'caption': caption,
        })
    contracts = ContractSnapshot.objects.first()
    if contracts and contracts.summary:
        summary = contracts.summary
        items.append({
            'icon': 'contrato', 'url_name': 'contratos:index',
            'label': f'Contratos com vigência em {contracts.fiscal_year}',
            'value': brl_compact(summary['contracted']),
            'caption': f'{summary["contracts"]} contratos com {summary["suppliers"]} fornecedores',
        })
    units = Unit.objects.count()
    if units:
        items.append({
            'icon': 'orgaos', 'url_name': 'unidades:list',
            'label': 'Órgãos e fundos cadastrados',
            'value': units, 'caption': 'com orçamento próprio no estado',
        })
    return items


def home(request):
    return render(request, 'pages/home/index.html', {
        'highlights': _highlights(),
        'money_path': MONEY_PATH,
        'upcoming': UPCOMING,
        'upcoming_count': UPCOMING_COUNT,
        'glossary': terms('receita', 'fundo', 'empenho', 'liquidacao', 'pagamento'),
    })


def glossary(request):
    return render(request, 'pages/glossary/index.html', {
        'glossary': TERMS.values(),
    })


def healthz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        return HttpResponse('unavailable', status=503, content_type='text/plain')
    return HttpResponse('ok', content_type='text/plain')


def page_not_found(request, exception):
    return render(request, 'pages/errors/error.html', {
        'error_code': 'NAVEGACAO-404',
        'error': PUBLIC_ERRORS['NAVEGACAO-404'],
        'action_url': reverse('home'),
        'action_label': 'Voltar ao início',
    }, status=404)


def server_error(request):
    return render(request, 'pages/errors/error.html', {
        'error_code': 'SISTEMA-500',
        'error': PUBLIC_ERRORS['SISTEMA-500'],
        'action_url': request.path,
        'action_label': 'Tentar novamente',
    }, status=500)
