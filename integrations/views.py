"""Páginas e consultas públicas; a importação ocorre em comandos separados."""

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render

from .models import Daily, SyncRun
from .selectors import top_creditors


def get_dailies(request):
    rows = list(
        Daily.objects.order_by('-date_inicied')
        .values('code_api', 'unit__code', 'recipient_name', 'date_inicied', 'date_return', 'value', 'destination')[:100]
    )
    return JsonResponse({'results': rows})


def get_list_credors_by_total_pago(request):
    creditors, legacy = top_creditors(settings.FIPLAN_SYNC_YEAR, settings.FIPLAN_NATURE_CODE)
    last_sync = SyncRun.objects.filter(
        status=SyncRun.Status.SUCCESS,
        fiscal_year=settings.FIPLAN_SYNC_YEAR,
        nature_code=settings.FIPLAN_NATURE_CODE,
    ).order_by('-finished_at', '-id').first()
    return render(request, 'pages/exec_orcament/index.html', {
        'units': creditors,
        'legacy': legacy,
        'year': settings.FIPLAN_SYNC_YEAR,
        'nature_code': settings.FIPLAN_NATURE_CODE,
        'last_sync': last_sync,
    })
