"""Converte os campos publicados pela fonte para o conjunto mínimo do portal."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

CPF_PATTERN = re.compile(r'(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)')
# A fonte publica o CPF mascarado, como ***.***.***-12 ou ***.123.456-**.
MASKED_CPF = re.compile(r'[*0-9]{3}\.[*0-9]{3}\.[*0-9]{3}-[*0-9]{2}')
CENT = Decimal('0.01')


def text(value, limit=255):
    if not isinstance(value, str) or len(value) > limit or CPF_PATTERN.search(value):
        return ''
    return value.strip()


def digits(value, limit=24):
    value = str(value)
    return value if re.fullmatch(rf'[0-9]{{1,{limit}}}', value) else ''


def process_link(value):
    if not isinstance(value, str) or len(value) > 500:
        return ''
    try:
        url = urlsplit(value)
        params = parse_qs(url.query, strict_parsing=True, max_num_fields=8)
    except ValueError:
        return ''
    if (url.scheme, url.netloc, url.path) != (
        'https', 'sei.rr.gov.br', '/sei/processo_acesso_externo_consulta.php',
    ):
        return ''
    # id_acesso_externo é a chave usada nos links públicos do SEI.
    ids = params.get('id_acesso_externo', [])
    if len(ids) != 1 or not digits(ids[0]) or len(ids[0]) == 11:
        return ''
    hashes = params.get('infra_hash', [])
    if len(hashes) != 1 or not re.fullmatch(r'[a-fA-F0-9]{16,128}', hashes[0]):
        return ''
    query = {'id_acesso_externo': ids[0], 'infra_hash': hashes[0]}
    return urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), ''))


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) >= 10**16 or amount != amount.quantize(CENT):
            raise ValueError('Valor de pagamento fora do formato esperado.')
    except InvalidOperation:
        raise ValueError('Valor de pagamento inválido.') from None
    return amount


def normalize(item, year, month):
    if not isinstance(item, dict):
        raise ValueError('Registro de pagamento inválido.')
    try:
        paid_on = date.fromisoformat(item['dataPagamento'])
        amount = money(item['valorPagamento'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('Data ou valor de pagamento inválido.') from None
    if (paid_on.year, paid_on.month) != (year, month):
        raise ValueError('Pagamento fora do mês solicitado.')
    number = digits(item.get('numeroPagamento'))
    unit_code = digits(item.get('codUnidadeOrcamentaria'), 20)
    unit_name = text(item.get('descUnidadeOrcamentaria'))
    if not number or not unit_code or not unit_name:
        raise ValueError('Pagamento sem documento ou unidade identificada.')

    raw_document = str(item.get('cpfCnpjCredor') or '').strip()
    document = re.sub(r'[.\-/\s]', '', raw_document).upper()
    if re.fullmatch(r'[0-9]{11}', document) or MASKED_CPF.fullmatch(raw_document):
        creditor_kind = 'person'
    elif re.fullmatch(r'[A-Z0-9]{12}[0-9]{2}', document):
        creditor_kind = 'company'
    else:
        creditor_kind = ''
    process = text(item.get('numeroProcesso'), 40) if creditor_kind == 'company' else ''

    return {
        'paid_on': paid_on,
        'amount': amount,
        'number': number,
        'unit_code': unit_code,
        'unit_name': unit_name,
        'nature_code': digits(item.get('codNaturezaDespesa'), 20),
        'nature_name': text(item.get('descNaturezaDespesa')),
        'expense_type': text(item.get('descTipoDespesa')),
        'creditor_kind': creditor_kind,
        'creditor_name': text(item.get('nomeCredor')) if creditor_kind == 'company' else '',
        'commitment': digits(item.get('numeroEmpenho')),
        'settlement': digits(item.get('numeroLiquidacao')),
        'process': process if re.fullmatch(r'[0-9./-]+', process) else '',
        'process_url': process_link(item.get('linkDeAcesso')) if creditor_kind == 'company' else '',
    }
