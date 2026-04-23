from django.db import connection
import asyncio

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
            'cnpj': row[1],
            'total_liquidado': row[2],
            'total_pago': row[3],
            'quantidade_pagamentos': row[4],
        })

    return results

def import_credors_by_fiplan():
    asyncio.run(get_list_credors_by_total_pago())