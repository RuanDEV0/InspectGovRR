import httpx
import environ
from django.core.cache import cache
from asgiref.sync import sync_to_async
env = environ.Env()
environ.Env.read_env()
from ..models import Unit, Credor

class FiplanAPI:
    BASE_URL = "https://api2.transparencia.rr.gov.br/transparencia"

async def get_token():
    url = FiplanAPI.BASE_URL + '/oauth/token?grant_type=client_credentials'
    api_username = env("FIPLAN_USERNAME")
    api_password = env("FIPLAN_PASSWORD")
    async with httpx.AsyncClient() as client:
        response = await client.post(url, auth=(api_username, api_password))
        if response.status_code == 200:
            data = response.json()
            cache.set('token', data['access_token'])
            return data['access_token']
        else :
            return "Erro em Buscar token"


async def get_dailies():
    token = cache.get('token')
    url = FiplanAPI.BASE_URL + '/api/v1/diarias/json'
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=None)
        if response.status_code == 200:

            data = response.json()
            return data
        else:
            return "Erro em Buscar Diarias"

async def get_units():
    token = cache.get('token')
    url = FiplanAPI.BASE_URL + '/api/v1/unidades-orcamentarias'
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return 'Erro em Buscar Unidades'

def bulk_create_credor(list):
    listCredor = [
        Credor(
            name=credor['credor'],
            cnpj=credor['identificacaoCredor'],
            total_pago=credor['totalPago'],
            total_liquidado=credor['totalLiquidado'],
            quantidade_pagamentos=credor['quantidadePagamentos']
        )
        for credor in list
    ]

    return Credor.objects.bulk_create(listCredor)

async def get_exec_orcamen_last_teen_years():
    token = cache.get('token')
    timeout = httpx.Timeout(60.0)
    units = await sync_to_async(list)(Unit.objects.all())
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"
               }
    for unit in units:
        url = FiplanAPI.BASE_URL + (f'/api/v1/execucao-orcamentaria/estatisticas-por-credor/'
                                    f'?exercicio=2025&limitePorPagina=50&mesInicio=1&mesFim=12'
                                    f'&unidadeOrcamentaria={unit.code}&codigoNaturezaDespesa=33903900')
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                await sync_to_async(bulk_create_credor)(data['listaCredores'])
            else:
                print("Erro ao buscar Credores - ", response.status_code, " - ", unit.name)
                print(response.content)
        print('Credores inseridos/atualizados da unidade - ', unit.name)