"""Consultas usadas pelas páginas públicas."""

import re
from decimal import Decimal

from django.db.models import Max, Sum

from integrations.models import CreditorSnapshot, Credor, SyncRun


def _money(value):
    formatted = f'{Decimal(value):,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return f'R$ {formatted}'


def _document(value):
    digits = re.sub(r'\D', '', str(value))
    if len(digits) == 14:
        return f'{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}'
    if len(digits) == 11:
        return f'***.***.***-{digits[-2:]}'
    return f'***{digits[-4:]}' if digits else 'Não informado'


def top_creditors(fiscal_year, nature_code):
    latest_run = SyncRun.objects.filter(
        status=SyncRun.Status.SUCCESS,
        fiscal_year=fiscal_year,
        nature_code=nature_code,
    ).order_by('-finished_at', '-id').first()
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
            'total_liquidado': _money(row['total_liquidado']),
            'total_pago': _money(row['total_pago']),
            'quantidade_pagamentos': row['quantidade_pagamentos'],
        }
        for row in rows
    ], legacy
