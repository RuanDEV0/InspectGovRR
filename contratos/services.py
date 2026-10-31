"""Coleta os contratos do ano; páginas públicas consultam somente o banco local."""

from contextlib import nullcontext
from datetime import datetime, timedelta

import httpx
from django.db import transaction
from django.utils import timezone

from integrations.fiplan_api.client import FiplanClient
from portal.formatting import LOCAL_TIME_ZONE

from .mappers import (
    aggregate, contract_records, normalize_additives, normalize_contracts,
    normalize_history, normalize_inspectors,
)
from .models import Contract, ContractDetail, ContractSnapshot

# Limita o custo por ciclo; detalhes pendentes continuam na próxima coleta.
DETAIL_LIMIT = 1000
DETAIL_STALE_AFTER = timedelta(days=7)
MAX_CONSECUTIVE_FAILURES = 5


def local_today():
    return datetime.now(LOCAL_TIME_ZONE).date()


def _api(client):
    return nullcontext(client) if client is not None else FiplanClient()


def sync_contracts(*, client=None, year=None, today=None):
    year = year or (today or local_today()).year
    if not 2000 <= year <= 9999:
        raise ValueError('Ano inválido.')
    start, end = f'{year}-01-01', f'{year}-12-31'
    with _api(client) as api:
        contracts = normalize_contracts(api.get_contracts(start, end))
        # A exportação não informa o total; a listagem paginada confirma se veio completa.
        page = api.get_contracts_page(start, end, page=0, size=1)
        history = normalize_history(api.get_contract_yearly_totals(), year)
    try:
        expected = int(page['totalElements'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Total de contratos ausente na listagem paginada.') from exc
    if len(contracts) != expected:
        raise ValueError(
            f'A exportação trouxe {len(contracts)} de {expected} contratos. Dados anteriores preservados.'
        )
    data = aggregate(contracts, year)
    records = [Contract(fiscal_year=year, **record) for record in contract_records(contracts)]
    with transaction.atomic():
        snapshot, _ = ContractSnapshot.objects.update_or_create(
            fiscal_year=year, defaults={**data, 'history': history},
        )
        Contract.objects.filter(fiscal_year=year).delete()
        Contract.objects.bulk_create(records)
        # Detalhes de contratos que saíram de todas as listas não são mais exibidos.
        ContractDetail.objects.exclude(contract_id__in=Contract.objects.values('contract_id')).delete()
    return snapshot


def pending_details(contracts, known, now):
    """Fila de coleta: contratos sem detalhe, depois alterados, depois os mais antigos."""
    missing, changed, stale = [], [], []
    for contract in sorted(contracts, key=lambda contract: (-contract.contracted, contract.contract_id)):
        detail = known.get(contract.contract_id)
        if detail is None:
            missing.append(contract)
        elif detail.signature != contract.signature:
            changed.append(contract)
        elif detail.fetched_at <= now - DETAIL_STALE_AFTER:
            stale.append(contract)
    stale.sort(key=lambda contract: known[contract.contract_id].fetched_at)
    return missing + changed + stale


def sync_contract_details(year, *, client=None, limit=DETAIL_LIMIT, now=None):
    """Coleta aditivos e fiscais aos poucos. O que já foi salvo continua valendo se a coleta parar."""
    now = now or timezone.now()
    contracts = list(Contract.objects.filter(fiscal_year=year).only(
        'contract_id', 'contracted', 'signature', 'has_changes',
    ))
    known = {detail.contract_id: detail for detail in ContractDetail.objects.filter(
        contract_id__in=[contract.contract_id for contract in contracts],
    ).only('contract_id', 'signature', 'fetched_at')}
    queue = pending_details(contracts, known, now)
    counts = {'updated': 0, 'failed': 0, 'pending': max(len(queue) - limit, 0)}
    failures_in_row = 0
    with _api(client) as api:
        for contract in queue[:limit]:
            contract_id = contract.contract_id
            try:
                additives = (normalize_additives(api.get_contract_additives(contract_id), contract_id)
                             if contract.has_changes else [])
                inspectors = normalize_inspectors(api.get_contract_inspectors(contract_id), contract_id)
            except (httpx.HTTPError, ValueError) as exc:
                counts['failed'] += 1
                failures_in_row += 1
                if failures_in_row >= MAX_CONSECUTIVE_FAILURES:
                    raise ValueError(
                        f'{failures_in_row} contratos seguidos falharam (último: {contract_id}, '
                        f'{type(exc).__name__}: {exc}); {counts["updated"]} detalhes salvos.'
                    ) from exc
                continue
            failures_in_row = 0
            ContractDetail.objects.update_or_create(contract_id=contract_id, defaults={
                'signature': contract.signature, 'additives': additives,
                'inspectors': inspectors, 'fetched_at': now,
            })
            counts['updated'] += 1
    return counts


def describe_contracts(snapshot):
    summary = snapshot.summary
    return (f'Contratos atualizados: {summary["contracts"]} contratos, '
            f'{summary["suppliers"]} fornecedores, vigência em {snapshot.fiscal_year}.')


def describe_details(counts):
    return (f'Aditivos e fiscais: {counts["updated"]} contratos atualizados, '
            f'{counts["failed"]} falhas, {counts["pending"]} para as próximas coletas.')
