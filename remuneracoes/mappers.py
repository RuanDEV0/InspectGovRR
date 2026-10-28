"""Adapta os campos documentados sem inferir irregularidade ou vínculo ativo."""

import re
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.utils.crypto import salted_hmac

from portal.formatting import brl

TOP_LIMIT = 50
MINIMUM_WAGES = {
    2026: {
        'amount': Decimal('1621.00'),
        'source': 'https://www2.camara.leg.br/legin/fed/decret/2025/decreto-12797-23-dezembro-2025-798569-norma-pe.html',
        'label': 'Decreto nº 12.797/2025',
    },
}


def money(value, *, optional=False):
    if optional and value is None:
        return None
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) >= Decimal('1e16'):
            raise ValueError
        return str(amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Valor monetário inválido na folha.') from exc


def text(value):
    return str(value).strip() if value is not None else ''


def person_key(value):
    raw = text(value)
    if not re.fullmatch(r'[\d.\-]+', raw):
        raise ValueError('Identificação ausente ou incompleta na folha.')
    digits = re.sub(r'\D', '', raw)
    if len(digits) != 11:
        raise ValueError('Identificação ausente ou incompleta na folha.')
    return digits


def check_period(item, year, month):
    if not isinstance(item, dict):
        raise ValueError('Registro inválido na folha.')
    try:
        matches = int(item['ano']) == year and int(item['mes']) == month
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError('Competência ausente na folha.') from exc
    if not matches:
        raise ValueError('A API retornou uma competência diferente da solicitada.')


def normalize_ranking(payload, year, month):
    if not isinstance(payload, list):
        raise ValueError('Formato inválido do ranking de remunerações.')
    rows, seen = [], set()
    for item in payload:
        check_period(item, year, month)
        cpf = person_key(item.get('cpf'))
        name, agency = text(item.get('nome')), text(item.get('orgao'))
        key = (cpf, agency)
        if not name or not agency or key in seen:
            raise ValueError('Ranking com identificação ausente ou registro duplicado.')
        seen.add(key)
        identifier = salted_hmac('payroll-public-id', f'{year}:{month}:{cpf}:{agency}').hexdigest()[:32]
        rows.append({
            'id': str(uuid.UUID(identifier)), 'name': name, 'agency': agency,
            'amount': money(item.get('valorTotalBruto')), '_cpf': cpf,
        })
    rows.sort(key=lambda row: (-Decimal(row['amount']), row['name'], row['id']))
    return [{**row, 'position': position} for position, row in enumerate(rows[:TOP_LIMIT], 1)]


def matches_person(item, cpf, expected_name):
    raw = text(item.get('cpf'))
    mask = re.fullmatch(r'##(\d{3})\.(\d{3})##', raw)
    if mask:
        # Formato observado da Fiplan: seis dígitos centrais e nome completo.
        same_name = bool(expected_name) and ' '.join(text(item.get('nome')).casefold().split()) == ' '.join(expected_name.casefold().split())
        return same_name and ''.join(mask.groups()) == cpf[3:9]
    return person_key(raw) == cpf


def normalize_details(records, cpf, year, month, expected_name=None):
    statements, memberships, seen = [], [], set()
    for item in records:
        check_period(item, year, month)
        # A busca por CPF aceita correspondência parcial: confirme a identidade.
        if not matches_person(item, cpf, expected_name):
            raise ValueError('O detalhamento retornou uma pessoa diferente da solicitada.')
        links = item.get('matriculas')
        if links is not None and not isinstance(links, list):
            raise ValueError('Formato inválido de matrículas.')
        for link in links or []:
            if not isinstance(link, dict):
                raise ValueError('Matrícula inválida.')
            registration, agency = text(link.get('matricula')), text(link.get('orgao'))
            if not registration or not agency:
                continue
            key = (registration, agency)
            if key not in seen:
                seen.add(key)
                memberships.append({
                    'agency': agency, 'role': text(link.get('cargo')),
                    'category': text(link.get('tipoCargo')), 'level': text(link.get('nivel')),
                })
        events = item.get('lancamentos') or []
        if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
            raise ValueError('Formato inválido dos lançamentos.')
        statements.append({
            'agency': text(item.get('orgao')), 'role': text(item.get('cargo')),
            'base': money(item.get('vencimento'), optional=True),
            'other': money(item.get('proventosDiversos'), optional=True),
            'mandatory': money(item.get('deducoesObrigatorias'), optional=True),
            'authorized': money(item.get('deducoesAutorizadas'), optional=True),
            'gross': money(item.get('remuneracaoBruta'), optional=True),
            'net': money(item.get('remuneracaoLiquida'), optional=True),
            'events': [{
                'name': text(event.get('evento')) or 'Lançamento sem descrição',
                'kind': text(event.get('tipoEvento')),
                'amount': money(event.get('valor'), optional=True),
            } for event in events],
        })
    return {'statements': statements, 'memberships': memberships, 'membership_count': len(memberships)}


def present_row(row, year):
    wage = MINIMUM_WAGES.get(year)
    equivalent = None
    if wage and Decimal(row['amount']) > 0:
        equivalent = str((Decimal(row['amount']) / wage['amount']).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)).replace('.', ',')
    return {**row, 'full_amount': brl(row['amount']), 'equivalent': equivalent}
