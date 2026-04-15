from django.db import connection
import asyncio

def get_list_credors_by_total_pago():
    with connection.cursor() as cursor:
        cursor.execute("select c.name, c.cnpj, c.total_liquidado, sum(c.total_pago), c.quantidade_pagamentos"
                       " from integrations_credor as c group by c.name, c.cnpj, c.total_liquidado, c.quantidade_pagamentos, c.total_pago "
                       "order by c.total_pago desc limit 10")

        return cursor.fetchall()

def import_credors_by_fiplan():
    asyncio.run(get_list_credors_by_total_pago())