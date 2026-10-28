"""Páginas e consultas públicas; a importação ocorre em comandos separados."""

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render

from portal.formatting import local_datetime
from portal.glossary import terms

from .models import Daily
from .selectors import latest_successful_run, nature_label, top_creditors


def get_dailies(request):
    rows = list(
        Daily.objects.order_by('-date_inicied')
        .values('code_api', 'unit__code', 'recipient_name', 'date_inicied', 'date_return', 'value', 'destination')[:100]
    )
    return JsonResponse({'results': rows})


def get_list_credors_by_total_pago(request):
    creditors, legacy = top_creditors(settings.FIPLAN_SYNC_YEAR, settings.FIPLAN_NATURE_CODE)
    last_sync = latest_successful_run(settings.FIPLAN_SYNC_YEAR, settings.FIPLAN_NATURE_CODE)
    return render(request, 'pages/exec_orcament/index.html', {
        'creditors': creditors,
        'legacy': legacy,
        'status': 'Dados anteriores à coleta por período' if legacy else '',
        'period_label': 'Período não informado' if legacy else f'Ano de {settings.FIPLAN_SYNC_YEAR}',
        'updated_at': local_datetime(last_sync.finished_at) if last_sync else '',
        'nature': nature_label(settings.FIPLAN_NATURE_CODE),
        'glossary': terms('credor', 'liquidacao', 'pagamento', 'natureza'),
    })
