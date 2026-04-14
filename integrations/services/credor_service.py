from django.db import connection


def get_list_credors_by_total_pago():
    with connection.cursor() as cursor:
        cursor.execute("select c.name, c.cnpj, c.total_liquidado, sum(c.total_pago), c.quantidade_pagamentos"
                       " from integrations_credor as c group by c.name, c.cnpj, c.total_liquidado, c.quantidade_pagamentos")

        return cursor.fetchall()