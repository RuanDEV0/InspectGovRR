"""Orquestra uma coleta e registra seu resultado."""

from contextlib import nullcontext

from django.conf import settings
from django.utils import timezone

from integrations.fiplan_api.client import FiplanClient
from integrations.models import CreditorSnapshot, SyncRun
from integrations.sync.creditors import sync_creditors
from integrations.sync.dailies import sync_dailies
from unidades.services import sync_units


def run_sync(*, fiscal_year=None, nature_code=None, include_dailies=None, client=None):
    fiscal_year = fiscal_year if fiscal_year is not None else settings.FIPLAN_SYNC_YEAR
    nature_code = nature_code if nature_code is not None else settings.FIPLAN_NATURE_CODE
    include_dailies = include_dailies if include_dailies is not None else settings.FIPLAN_SYNC_DIARIAS_ENABLED
    run = SyncRun.objects.create(fiscal_year=fiscal_year, nature_code=nature_code)
    counts = {}
    try:
        context = nullcontext(client) if client is not None else FiplanClient()
        with context as api:
            counts['units'] = sync_units(api)
            counts['creditors'] = sync_creditors(api, run, fiscal_year, nature_code)
            if include_dailies:
                counts['dailies'] = sync_dailies(api)
        run.status = SyncRun.Status.SUCCESS
        run.counts = counts
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'counts', 'finished_at'])
        return counts
    except Exception as exc:
        run.status = SyncRun.Status.FAILED
        run.error_message = str(exc)[:2000]
        run.counts = counts
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'error_message', 'counts', 'finished_at'])
        CreditorSnapshot.objects.filter(run=run).delete()
        raise
