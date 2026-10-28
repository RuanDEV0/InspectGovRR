"""Coleta um ranking pequeno de receita, sem chamadas à Fiplan nas páginas públicas."""

from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from integrations.fiplan_api.client import FiplanClient

from .models import RevenueSnapshot

RORAIMA_TIME_ZONE = ZoneInfo('America/Boa_Vista')
TOP_LIMIT = 5


def current_period(today=None):
    today = today or datetime.now(RORAIMA_TIME_ZONE).date()
    return today.year, 1, today.month


def normalize_ranking(payload, fiscal_year):
    if not isinstance(payload, list) or not payload:
        raise ValueError('A Fiplan não retornou unidades para o ranking de receita')

    rows = []
    seen_codes = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError('Registro de receita inválido na resposta Fiplan')
        try:
            raw_code = item['codUnidadeOrcamentaria']
            raw_name = item['descUnidadeOrcamentaria']
            if raw_code is None or raw_name is None:
                raise ValueError('Unidade orçamentária ausente')
            code = str(raw_code).strip()
            name = str(raw_name).strip()
            year = int(item['codExercicio'])
            amount = Decimal(str(item['valorRealizacaoMes']))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError('Campos de receita inválidos na resposta Fiplan') from exc
        if not code or not name or year != fiscal_year or not amount.is_finite():
            raise ValueError('Unidade, exercício ou valor inválido na resposta Fiplan')
        if code in seen_codes:
            raise ValueError(f'Unidade orçamentária repetida na resposta Fiplan: {code}')
        seen_codes.add(code)
        rows.append({
            'unit_code': code,
            'unit_name': name,
            'amount': str(amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        })

    rows.sort(key=lambda row: (-Decimal(row['amount']), row['unit_code']))
    return rows[:TOP_LIMIT]


def sync_revenue(*, client=None, today=None):
    fiscal_year, month_start, month_end = current_period(today)
    context = nullcontext(client) if client is not None else FiplanClient()
    with context as api:
        payload = api.get_top_revenue_units(fiscal_year, month_start, month_end, TOP_LIMIT)
    rows = normalize_ranking(payload, fiscal_year)
    snapshot, _ = RevenueSnapshot.objects.update_or_create(
        fiscal_year=fiscal_year,
        month_start=month_start,
        month_end=month_end,
        defaults={'rows': rows},
    )
    return snapshot
