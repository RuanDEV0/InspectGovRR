"""Coleta completa de um exercício; o CPF é usado somente em memória."""

from collections import Counter
from contextlib import nullcontext
from datetime import datetime
import json

from django.db import transaction

from integrations.fiplan_api.client import FiplanClient
from portal.formatting import LOCAL_TIME_ZONE

from .mappers import aggregate, normalize, reconcile
from .models import DailySnapshot, DailyTrip

PAGE_SIZE = 100
MAX_UNIT_PAGES = 100


def local_year():
    return datetime.now(LOCAL_TIME_ZONE).year


def _api(client):
    return nullcontext(client) if client is not None else FiplanClient()


def total_elements(payload):
    try:
        total = int(payload['totalElements'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Total de diárias ausente na listagem paginada') from exc
    if total < 0:
        raise ValueError('Total de diárias inválido')
    return total


def add_items(found, items):
    """Indexa por empenho, o único identificador estável que a fonte oferece por viagem."""
    if not isinstance(items, list):
        raise ValueError('Lista de diárias inválida')
    for item in items:
        if not isinstance(item, dict) or not str(item.get('numeroEmpenho') or '').strip():
            raise ValueError('Diária sem número de empenho')
        key = str(item['numeroEmpenho']).strip()
        prior = found.get(key)
        if prior is not None and json.dumps(prior, sort_keys=True) != json.dumps(item, sort_keys=True):
            raise ValueError('Empenho repetido com dados diferentes')
        found[key] = item
    return found


def unit_codes(payload):
    if not isinstance(payload, list):
        raise ValueError('Resposta de unidades da Fiplan deve ser uma lista')
    return [
        str(code) for item in payload
        if (code := item.get('codigoUnidadeOrcamentaria') or item.get('codigoUnidadeorcamentaria'))
    ]


def add_missing_by_unit(api, year, found, expected):
    """Busca por órgão o que a exportação omite, como lançamentos sem data de viagem.

    Consultar órgão a órgão mantém cada listagem curta: a API só ordena por campos
    não únicos, e uma paginação longa repete e perde registros entre as páginas.
    """
    counts = Counter(str(item.get('cdUnidadeOrcamentaria') or '').strip() for item in found.values())
    for code in unit_codes(api.get_units()):
        if len(found) >= expected:
            return
        first = api.get_new_dailies(year, page=0, size=PAGE_SIZE, unit=code)
        if total_elements(first) == counts[code]:
            continue
        pages = int(first.get('totalPages') or 0)
        if pages > MAX_UNIT_PAGES:
            raise ValueError('Limite de páginas de diárias excedido')
        add_items(found, first.get('content'))
        for page in range(1, pages):
            add_items(found, api.get_new_dailies(year, page=page, size=PAGE_SIZE, unit=code).get('content'))


def sync_dailies(*, year, client=None):
    if not 2000 <= year <= 9999:
        raise ValueError('Exercício inválido')
    with _api(client) as api:
        # A exportação não informa o total; a listagem paginada confirma se veio completa.
        expected = total_elements(api.get_new_dailies(year, page=0, size=1))
        found = add_items({}, api.get_dailies_export(year))
        if len(found) < expected:
            add_missing_by_unit(api, year, found, expected)
        official = api.get_dailies_agency_totals(year)
    if len(found) != expected:
        raise ValueError(f'A coleta trouxe {len(found)} de {expected} diárias. Dados anteriores preservados.')
    trips, lump_sums = [], []
    for item in found.values():
        record = normalize(item, year)
        (lump_sums if record['kind'] == 'lump_sum' else trips).append(record)
    reconciled = reconcile(trips, lump_sums, official)
    summary = aggregate(trips, lump_sums, reconciled=reconciled)
    records = [
        DailyTrip(year=year, **{key: value for key, value in trip.items() if key != 'kind'})
        for trip in trips
    ]
    with transaction.atomic():
        snapshot, _ = DailySnapshot.objects.update_or_create(
            year=year, defaults={'summary': summary, 'source_count': expected},
        )
        DailyTrip.objects.filter(year=year).delete()
        DailyTrip.objects.bulk_create(records, batch_size=1000)
    return snapshot


def describe_dailies(snapshot):
    summary = snapshot.summary
    return (f'Diárias atualizadas: {summary["trips"]} viagens em {snapshot.year}, '
            f'{len(summary["lump_sums"])} lançamentos sem detalhe.')
