"""Coleta limitada ao ranking; páginas públicas consultam somente o banco local."""

from contextlib import nullcontext
from datetime import datetime
import json

from django.db import transaction

from integrations.fiplan_api.client import FiplanClient
from portal.formatting import LOCAL_TIME_ZONE

from .mappers import TOP_LIMIT, normalize_details, normalize_ranking
from .models import PayrollSnapshot

MAX_DETAIL_PAGES = 10


def recent_periods(today=None):
    today = today or datetime.now(LOCAL_TIME_ZONE).date()
    for offset in range(12):
        year, month = divmod(today.year * 12 + today.month - 1 - offset, 12)
        yield year, month + 1


def fetch_details(api, year, month, cpf, expected_name=None):
    records, seen, expected_pages, expected_total = [], set(), None, None
    for page in range(MAX_DETAIL_PAGES):
        payload = api.get_payroll_details(year, month, cpf, page=page, size=100)
        if not isinstance(payload, dict) or not isinstance(payload.get('content'), list):
            raise ValueError('Formato inválido da página de remunerações.')
        try:
            pages, total, number = int(payload['totalPages']), int(payload['totalElements']), int(payload['number'])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('Paginação de remunerações ausente ou inválida.') from exc
        if number != page or not 0 <= pages <= MAX_DETAIL_PAGES or total < 0:
            raise ValueError('Paginação de remunerações fora do limite esperado.')
        if expected_pages is not None and (pages, total) != (expected_pages, expected_total):
            raise ValueError('A paginação mudou durante a coleta. Tente novamente.')
        expected_pages, expected_total = pages, total
        content = payload['content']
        signature = json.dumps(content, sort_keys=True)
        if signature in seen or (not content and total):
            raise ValueError('A API repetiu ou omitiu uma página de remunerações.')
        seen.add(signature)
        records.extend(content)
        if page + 1 >= pages:
            if len(records) != total:
                raise ValueError('Detalhamento incompleto na resposta da API.')
            return normalize_details(records, cpf, year, month, expected_name)
    raise ValueError('O detalhamento ultrapassou o limite de páginas.')


def sync_payroll(*, client=None, year=None, month=None, today=None):
    if (year is None) != (month is None):
        raise ValueError('Informe ano e mês juntos.')
    if year is not None and (not 2000 <= year <= 9999 or not 1 <= month <= 12):
        raise ValueError('Ano ou mês inválido.')
    periods = [(year, month)] if year is not None else recent_periods(today)
    context = nullcontext(client) if client is not None else FiplanClient()
    with context as api:
        for candidate_year, candidate_month in periods:
            rows = normalize_ranking(
                api.get_payroll_ranking(candidate_year, candidate_month, TOP_LIMIT),
                candidate_year, candidate_month,
            )
            if rows:
                year, month = candidate_year, candidate_month
                break
        else:
            raise ValueError('Nenhuma remuneração disponível nos períodos consultados. Dados anteriores preservados.')
        details_by_person = {}
        for row in rows:
            cpf = row.pop('_cpf')
            if cpf not in details_by_person:
                details_by_person[cpf] = fetch_details(api, year, month, cpf, row['name'])
            row.update(details_by_person[cpf])
    # Publica somente após concluir e validar todas as consultas. Não armazena CPF.
    with transaction.atomic():
        snapshot, _ = PayrollSnapshot.objects.update_or_create(
            year=year, month=month, defaults={'rows': rows},
        )
    return snapshot
