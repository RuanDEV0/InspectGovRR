"""Consultas usadas pelas páginas públicas."""

import re

from django.db.models import Max, Sum

from integrations.models import CreditorSnapshot, Credor, SyncRun


# Naturezas de despesa conhecidas, descritas em linguagem simples.
NATURE_LABELS = {
    '33903900': 'Serviços prestados por empresas, como limpeza, manutenção, tecnologia e consultorias',
}


def nature_label(code):
    digits = re.sub(r'\D', '', str(code))
    official = f'{digits[0]}.{digits[1]}.{digits[2:4]}.{digits[4:6]}.{digits[6:8]}' if len(digits) == 8 else code
    return {'code': official, 'label': NATURE_LABELS.get(digits, '')}


def _document(value):
    digits = re.sub(r'\D', '', str(value))
    if len(digits) == 14:
        return f'{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}'
    if len(digits) == 11:
        return f'***.***.***-{digits[-2:]}'
    return f'***{digits[-4:]}' if digits else 'Não informado'


def latest_successful_run(fiscal_year, nature_code):
    return SyncRun.objects.filter(
        status=SyncRun.Status.SUCCESS,
        fiscal_year=fiscal_year,
        nature_code=nature_code,
    ).order_by('-finished_at', '-id').first()


def top_creditors(fiscal_year, nature_code):
    latest_run = latest_successful_run(fiscal_year, nature_code)
    rows = list(
        CreditorSnapshot.objects.filter(run=latest_run)
        .values('identifier')
        .annotate(
            display_name=Max('name'),
            total_liquidado=Sum('total_liquidado'),
            total_pago=Sum('total_pago'),
            quantidade_pagamentos=Sum('quantidade_pagamentos'),
        )
        .order_by('-total_pago')[:10]
    )
    legacy = False
    if latest_run is None:
        rows = list(
            Credor.objects.values('cnpj')
            .annotate(
                display_name=Max('name'),
                total_liquidado=Sum('total_liquidado'),
                total_pago=Sum('total_pago'),
                quantidade_pagamentos=Sum('quantidade_pagamentos'),
            )
            .order_by('-total_pago')[:10]
        )
        legacy = bool(rows)
    return [
        {
            'name': row['display_name'],
            'document': _document(row['cnpj'] if legacy else row['identifier']),
            'total_liquidado': row['total_liquidado'],
            'total_pago': row['total_pago'],
            'quantidade_pagamentos': row['quantidade_pagamentos'],
        }
        for row in rows
    ], legacy
