"""Importação de estatísticas por credor, separadas por unidade e exercício."""

from decimal import Decimal, InvalidOperation
import re

from django.db import transaction

from integrations.models import CreditorSnapshot
from unidades.models import Unit

PAGE_SIZE = 50
MAX_PAGES = 1000


def _fetch_all(client, run, unit, fiscal_year, nature_code):
    records = []
    identifiers = set()
    for page in range(1, MAX_PAGES + 1):
        payload = client.get_creditor_stats(unit.code, fiscal_year, nature_code, page, PAGE_SIZE)
        if not isinstance(payload, dict) or not isinstance(payload.get('listaCredores'), list):
            raise ValueError(f'Resposta de credores inválida para a unidade {unit.code}')
        items = payload['listaCredores']
        for item in items:
            identifier = re.sub(r'\D', '', str(item.get('identificacaoCredor') or ''))
            if not identifier or identifier in identifiers:
                raise ValueError(f'Identificador de credor ausente ou repetido na unidade {unit.code}')
            identifiers.add(identifier)
            try:
                records.append(CreditorSnapshot(
                    run=run,
                    unit=unit,
                    identifier=identifier,
                    name=item['credor'],
                    fiscal_year=fiscal_year,
                    nature_code=nature_code,
                    total_pago=Decimal(str(item['totalPago'])),
                    total_liquidado=Decimal(str(item['totalLiquidado'])),
                    quantidade_pagamentos=int(item['quantidadePagamentos']),
                ))
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                raise ValueError(f'Dados de credor inválidos na unidade {unit.code}') from exc
        if len(items) < PAGE_SIZE:
            return records
    raise ValueError(f'Limite de páginas excedido na unidade {unit.code}')


def sync_creditors(client, run, fiscal_year, nature_code):
    count = 0
    for unit in Unit.objects.order_by('code'):
        records = _fetch_all(client, run, unit, fiscal_year, nature_code)
        with transaction.atomic():
            CreditorSnapshot.objects.bulk_create(records, batch_size=500)
        count += len(records)
    return count
