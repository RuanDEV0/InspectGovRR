import asyncio
import locale
import re

from django.db import connection

locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

def get_list_credors_by_total_pago():
    with connection.cursor() as cursor:
        cursor.execute("select c.name,c.cnpj, ROUND(sum(c.total_liquidado)::numeric, 2), ROUND(sum(c.total_pago)::numeric, 2) as pago_formatado, sum(c.quantidade_pagamentos)"
                       " from integrations_credor as c group by c.cnpj, c.name "
                       "order by pago_formatado desc limit 10")

        rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append({
            'name': row[0],
            'cnpj': formatter_cnpj(row[1]),
            'total_liquidado': locale.currency(row[2], grouping=True, symbol=True),
            'total_pago': locale.currency(row[3], grouping=True, symbol=True),
            'quantidade_pagamentos': row[4],
        })

    return results

def import_credors_by_fiplan():
    asyncio.run(get_list_credors_by_total_pago())

def formatter_cnpj(data):
    cnpj_limpo = re.sub(r'\D', '', str(data))

    cnpj_formatado = cnpj_limpo.zfill(14)

    return f"{cnpj_formatado[:2]}.{cnpj_formatado[2:5]}.{cnpj_formatado[5:8]}/{cnpj_formatado[8:12]}-{cnpj_formatado[12:]}"