from django.db import connection
import asyncio, locale, re
locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

def get_list_credors_by_total_pago():
    with connection.cursor() as cursor:
        cursor.execute("select c.name,c.cnpj, ROUND(sum(c.total_liquidado)::numeric, 2), ROUND(sum(c.total_pago)::numeric, 2) as pago_formatado, sum(c.quantidade_pagamentos)"
                       " from integrations_credor as c group by c.name, c.cnpj "
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

def formatter_cnpj(cnpj):
    cnpj = re.sub(r'\D', '', str(cnpj))
    return re.sub(r'(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})', r'\1.\2.\3/\4-\5', cnpj)