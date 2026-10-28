"""Importação de unidades orçamentárias."""

from django.db import transaction

from .models import Unit


def sync_units(client):
    payload = client.get_units()
    if not isinstance(payload, list):
        raise ValueError('Resposta de unidades da Fiplan deve ser uma lista')

    count = 0
    with transaction.atomic():
        for item in payload:
            code = item.get('codigoUnidadeOrcamentaria') or item.get('codigoUnidadeorcamentaria')
            name = item.get('descricaoUnidadeOrcamentaria')
            if not code or not name:
                raise ValueError('Unidade Fiplan sem código ou descrição')
            Unit.objects.update_or_create(
                code=str(code),
                defaults={'name': name, 'acronym': item.get('sigla')},
            )
            count += 1
    return count
