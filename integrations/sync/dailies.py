"""Importação opcional de diárias com identificação estável da API."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction

from integrations.models import Daily
from unidades.models import Unit


def _parse_date(value):
    if isinstance(value, date):
        return value
    for pattern in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(str(value), pattern).date()
        except ValueError:
            continue
    raise ValueError(f'Data de diária inválida: {value}')


def sync_dailies(client):
    payload = client.get_dailies()
    items = payload.get('content') if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError('Resposta de diárias da Fiplan deve conter uma lista')

    units = {unit.code: unit for unit in Unit.objects.all()}
    count = 0
    with transaction.atomic():
        for item in items:
            code = next((item.get(key) for key in ('idDiaria', 'codigoDiaria', 'id', 'codigo') if item.get(key)), None)
            unit_code = str(item.get('codUnidadeOrcamentaria') or '')
            if not code or unit_code not in units:
                raise ValueError('Diária sem identificador estável ou unidade cadastrada')
            try:
                Daily.objects.update_or_create(
                    code_api=str(code),
                    defaults={
                        'unit': units[unit_code],
                        'recipient_name': item['nomeCredor'],
                        'position': item.get('cargo'),
                        'date_inicied': _parse_date(item['dataInicio']),
                        'date_return': _parse_date(item['dataRetorno']),
                        'value': Decimal(str(item['valor'])),
                        'reason': item.get('motivo'),
                        'destination': item.get('localidade'),
                    },
                )
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                raise ValueError(f'Dados inválidos na diária {code}') from exc
            count += 1
    return count
