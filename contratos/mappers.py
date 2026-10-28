"""Agrega contratos por fornecedor e por órgão sem inferir irregularidade.

Alcance e concentração são fatos contábeis, não indícios por si só: fornecedores
de água, energia ou passagens atendem muitos órgãos por natureza, e uma fatia
alta pode vir de um único contrato grande. As páginas exibem essa ressalva.
"""

import html
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.utils.crypto import salted_hmac

AGENCY_TOP = 5
# Selo de concentração: fatia mínima num órgão que tenha concorrência, para não
# destacar órgãos com apenas um ou dois fornecedores.
CONCENTRATION_PERCENT = Decimal('50')
CONCENTRATION_MIN_SUPPLIERS = 3
HISTORY_YEARS = 10
ZERO = Decimal('0.00')
SEI_PREFIX = 'https://sei.rr.gov.br/'
# Rótulos confirmados no detalhe do contrato da própria API; outros códigos não têm nome na fonte.
ADDITIVE_KINDS = {10037: 'Prorrogação de prazo', 10038: 'Acréscimo de valor'}


def money(value, *, optional=False):
    # Pago, liquidado e aditivos vêm nulos quando ainda não há registro.
    if optional and value is None:
        return ZERO
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) >= Decimal('1e16'):
            raise ValueError
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Valor monetário inválido nos contratos.') from exc
    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def text(value):
    # Alguns nomes chegam com entidades HTML, como "COLET&#1040;".
    return ' '.join(html.unescape(str(value)).split()) if value is not None else ''


def date_part(value):
    try:
        return date.fromisoformat(text(value)[:10])
    except ValueError:
        return None


def document_digits(value):
    digits = re.sub(r'\D', '', text(value))
    # Documentos guardados como número perdem o zero à esquerda.
    if len(digits) in (10, 13):
        digits = '0' + digits
    return digits if len(digits) in (11, 14) else ''


def display_document(digits):
    if len(digits) == 14:
        return f'{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}'
    return f'***.***.***-{digits[-2:]}'


def percent(part, whole):
    if whole <= 0:
        return '0.0'
    return str((max(part, ZERO) / whole * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def supplier_id(digits):
    return salted_hmac('contract-supplier-id', digits).hexdigest()[:16]


def normalize_contracts(payload):
    if not isinstance(payload, list) or not payload:
        raise ValueError('A Fiplan não retornou contratos para o período.')
    contracts, seen = [], set()
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError('Registro de contrato inválido.')
        try:
            contract_id = int(item['idContrato'])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('Contrato sem identificador na resposta Fiplan.') from exc
        if contract_id in seen:
            raise ValueError(f'Contrato repetido na resposta Fiplan: {contract_id}')
        seen.add(contract_id)
        digits = document_digits(item.get('cpfCnpjContratado'))
        name = text(item.get('nomeContratado'))
        agency_code = text(item.get('codigoUnidadeOrcamentaria'))
        agency_name = text(item.get('orgaoContratante'))
        if not digits or not name or not agency_code or not agency_name:
            raise ValueError(f'Contrato {contract_id} sem contratado ou órgão identificado.')
        original_end = date_part(item.get('dataFimVigenciaContrato'))
        sei_url = text(item.get('linkProcessoSei'))
        contracts.append({
            'id': contract_id, 'document': digits, 'name': name,
            'agency_code': agency_code, 'agency_name': agency_name,
            'signed_year': text(item.get('exercicioContrato')),
            'number': text(item.get('numeroContratoFormatado')),
            'subject': text(item.get('objetoDoContrato')),
            'kind': text(item.get('tipoContrato')),
            'situation': text(item.get('situacaoContrato')),
            'signed_at': date_part(item.get('dataAssinaturaContrato')),
            'start': date_part(item.get('dataInicioVigenciaContrato')),
            'end': date_part(item.get('dataFimVigenciaContratoAditivado')) or original_end,
            'original_end': original_end,
            'original': money(item['valorContrato']) if item.get('valorContrato') is not None else None,
            'contracted': money(item.get('valorTotalContrato')),
            'liquidated': money(item.get('valorTotalLiquidado'), optional=True),
            'paid': money(item.get('valorTotalPago'), optional=True),
            'additives': money(item.get('valorTotalAditivos'), optional=True),
            'sei_number': text(item.get('numeroProcessoSei')),
            # Só links do SEI de Roraima; o campo às vezes traz "#".
            'sei_url': sei_url if sei_url.startswith(SEI_PREFIX) else '',
        })
    return contracts


def extended(end, original_end):
    """O prazo atual passa do fim original: houve prorrogação."""
    return bool(end and original_end and end > original_end)


def contract_records(contracts):
    """Linhas da tabela de contratos, sem o documento do contratado."""
    records = []
    for contract in contracts:
        record = {key: contract[key] for key in (
            'number', 'subject', 'kind', 'situation', 'signed_at', 'start', 'end', 'original_end',
            'original', 'contracted', 'additives', 'liquidated', 'paid', 'sei_number', 'sei_url',
            'agency_code', 'agency_name',
        )}
        records.append({
            **record, 'contract_id': contract['id'],
            'supplier_id': supplier_id(contract['document']), 'supplier_name': contract['name'],
            'has_changes': extended(contract['end'], contract['original_end']) or contract['additives'] > 0,
            # Muda quando há aditivo novo, prorrogação ou troca de situação: o detalhe é recoletado.
            'signature': f"{contract['additives']}|{contract['end']}|{contract['situation']}",
        })
    return records


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _detail_items(payload, contract_id, id_field):
    if not isinstance(payload, list):
        raise ValueError(f'Formato inválido no detalhe do contrato {contract_id}.')
    for item in payload:
        if not isinstance(item, dict) or _int_or_none(item.get(id_field)) != contract_id:
            raise ValueError(f'O detalhe do contrato {contract_id} trouxe registro de outro contrato.')
    return payload


def normalize_additives(payload, contract_id):
    rows = []
    for item in _detail_items(payload, contract_id, 'idContrato'):
        amount = next((money(item[key]) for key in ('valorAditivo', 'valrReajuste', 'valrApostilamento')
                       if item.get(key) is not None), None)
        rows.append({
            'label': text(item.get('numrControleTermoAditivo')),
            'kind': ADDITIVE_KINDS.get(_int_or_none(item.get('flagTipoAditivo')), 'Outra alteração'),
            'date': str(date_part(item.get('dataAditivo')) or date_part(item.get('dataPublicacaoDoe')) or ''),
            'start': str(date_part(item.get('dataInicioVigencia')) or ''),
            'end': str(date_part(item.get('dataTerminoVigencia')) or ''),
            # R$ 0,01 é usado na fonte para marcar prorrogação sem valor.
            'amount': str(amount) if amount is not None and amount > Decimal('0.01') else None,
            'reason': text(item.get('justificativa')),
        })
    rows.sort(key=lambda row: (row['date'], row['label']))
    return rows


def normalize_inspectors(payload, contract_id):
    rows, seen = [], set()
    for item in _detail_items(payload, contract_id, 'idenContrato'):
        name, role = text(item.get('nomeFiscalContrato')), text(item.get('cargoFiscal'))
        if not name or (name, role) in seen:
            continue
        seen.add((name, role))
        # Matrícula não é necessária para identificar o fiscal e fica de fora.
        rows.append({
            'name': name, 'role': role, 'unit': text(item.get('lotacaoFiscal')),
            'ordinance': text(item.get('numrPortaria')),
            'ordinance_date': str(date_part(item.get('dataPortaria')) or ''),
        })
    return rows


def _group(contracts, year):
    suppliers = defaultdict(lambda: {
        'latest': (-1, ''), 'contracts': 0, 'signed_in_year': 0,
        'contracted': ZERO, 'paid': ZERO, 'additives': ZERO,
        'agencies': defaultdict(lambda: {'contracted': ZERO, 'contracts': 0}),
    })
    agencies = defaultdict(lambda: {
        'latest': (-1, ''), 'contracts': 0, 'contracted': ZERO, 'paid': ZERO,
        'suppliers': defaultdict(lambda: ZERO),
    })
    signed_year = str(year)
    for contract in contracts:
        supplier = suppliers[contract['document']]
        # O nome do contrato mais recente representa o fornecedor e o órgão.
        supplier['latest'] = max(supplier['latest'], (contract['id'], contract['name']))
        supplier['contracts'] += 1
        supplier['signed_in_year'] += contract['signed_year'] == signed_year
        supplier['contracted'] += contract['contracted']
        supplier['paid'] += contract['paid']
        supplier['additives'] += contract['additives']
        link = supplier['agencies'][contract['agency_code']]
        link['contracted'] += contract['contracted']
        link['contracts'] += 1

        agency = agencies[contract['agency_code']]
        agency['latest'] = max(agency['latest'], (contract['id'], contract['agency_name']))
        agency['contracts'] += 1
        agency['contracted'] += contract['contracted']
        agency['paid'] += contract['paid']
        agency['suppliers'][contract['document']] += contract['contracted']
    return suppliers, agencies


def aggregate(contracts, year):
    suppliers, agencies = _group(contracts, year)
    names = {digits: supplier['latest'][1] for digits, supplier in suppliers.items()}
    agency_names = {code: agency['latest'][1] for code, agency in agencies.items()}

    agency_rows = []
    for code, agency in agencies.items():
        total = agency['contracted']
        ranked = sorted(agency['suppliers'].items(), key=lambda pair: (-pair[1], pair[0]))
        rest = ranked[AGENCY_TOP:]
        rest_total = sum((value for _, value in rest), ZERO)
        agency_rows.append({
            'code': code, 'name': agency_names[code],
            'contracted': str(total), 'paid': str(agency['paid']),
            'contracts': agency['contracts'], 'supplier_count': len(ranked),
            'top': [{
                'supplier': supplier_id(digits), 'name': names[digits],
                'contracted': str(value), 'percent': percent(value, total),
            } for digits, value in ranked[:AGENCY_TOP]],
            'others': {
                'count': len(rest), 'contracted': str(rest_total), 'percent': percent(rest_total, total),
            } if rest else None,
        })
    agency_rows.sort(key=lambda row: (-Decimal(row['contracted']), row['name']))

    supplier_rows = []
    for digits, supplier in suppliers.items():
        links = []
        for code, link in supplier['agencies'].items():
            links.append({
                'code': code, 'name': agency_names[code], 'contracts': link['contracts'],
                'contracted': str(link['contracted']),
                'percent': percent(link['contracted'], agencies[code]['contracted']),
            })
        links.sort(key=lambda link: (-Decimal(link['contracted']), link['name']))
        dominant = max(
            (link for link in links
             if len(agencies[link['code']]['suppliers']) >= CONCENTRATION_MIN_SUPPLIERS
             and Decimal(link['percent']) >= CONCENTRATION_PERCENT),
            key=lambda link: Decimal(link['percent']), default=None,
        )
        supplier_rows.append({
            'id': supplier_id(digits), 'name': names[digits],
            'document': display_document(digits),
            # Só CNPJ é publicado por extenso; CPF fica mascarado e fora do snapshot.
            'cnpj': digits if len(digits) == 14 else '',
            'contracts': supplier['contracts'], 'signed_in_year': supplier['signed_in_year'],
            'agency_count': len(links), 'area_count': len({code[:2] for code in supplier['agencies']}),
            'contracted': str(supplier['contracted']), 'paid': str(supplier['paid']),
            'additives': str(supplier['additives']),
            'agencies': links,
            'dominant': {'name': dominant['name'], 'percent': dominant['percent']} if dominant else None,
        })
    supplier_rows.sort(key=lambda row: (-Decimal(row['contracted']), row['name'], row['id']))

    summary = {
        'contracts': len(contracts), 'suppliers': len(supplier_rows), 'agencies': len(agency_rows),
        'signed_in_year': sum(row['signed_in_year'] for row in supplier_rows),
        'individuals': sum(1 for row in supplier_rows if not row['cnpj']),
        'dominant': sum(1 for row in supplier_rows if row['dominant']),
    }
    for key in ('contracted', 'liquidated', 'paid', 'additives'):
        summary[key] = str(sum((contract[key] for contract in contracts), ZERO))
    return {'summary': summary, 'agencies': agency_rows, 'suppliers': supplier_rows}


def normalize_history(payload, year):
    if not isinstance(payload, list):
        raise ValueError('Formato inválido da série anual de contratos.')
    rows, seen = [], set()
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError('Registro inválido na série anual de contratos.')
        try:
            row_year = int(item['exercicioContrato'])
            count = int(item['quantidadeDeContratos'])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('Ano ou quantidade inválidos na série anual de contratos.') from exc
        if row_year in seen:
            raise ValueError(f'Ano repetido na série anual de contratos: {row_year}')
        seen.add(row_year)
        if row_year > year:
            continue
        rows.append({
            'year': row_year, 'contracts': count,
            'paid': str(money(item.get('valorTotalPago'), optional=True)),
            'largest': str(money(item.get('valorDoMaiorContrato'), optional=True)),
        })
    rows.sort(key=lambda row: -row['year'])
    return rows[:HISTORY_YEARS]
