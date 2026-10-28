"""Formatação de valores e datas compartilhada pelos módulos (padrão brasileiro)."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.utils import timezone

LOCAL_TIME_ZONE = ZoneInfo('America/Boa_Vista')
MONTHS = (
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
)

_SCALES = (
    (Decimal('1e9'), 'bilhão', 'bilhões'),
    (Decimal('1e6'), 'milhão', 'milhões'),
    (Decimal('1e3'), 'mil', 'mil'),
)


def _number(value, places):
    return f'{value:,.{places}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def brl(value):
    if value is None:
        return 'Não informado'
    return f'R$ {_number(Decimal(value), 2)}'


def brl_compact(value):
    """R$ 11,98 bilhões: leitura rápida; exiba o valor completo junto."""
    if value is None:
        return 'Não informado'
    amount = Decimal(value)
    for divisor, singular, plural in _SCALES:
        if abs(amount) >= divisor:
            scaled = (amount / divisor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            text = _number(scaled, 2).rstrip('0').rstrip(',')
            return f'R$ {text} {plural if abs(scaled) >= 2 else singular}'
    return brl(amount)


def br_date(value):
    """Data (ou texto ISO yyyy-mm-dd) no formato dd/mm/aaaa."""
    if not value:
        return ''
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return value.strftime('%d/%m/%Y')


def local_datetime(value):
    if value is None:
        return ''
    return timezone.localtime(value, LOCAL_TIME_ZONE).strftime('%d/%m/%Y às %H:%M')


def month_range(year, start, end):
    if start == end:
        return f'{MONTHS[start - 1]} de {year}'
    return f'{MONTHS[start - 1]} a {MONTHS[end - 1]} de {year}'
