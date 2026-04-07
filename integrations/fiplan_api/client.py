import httpx
import environ
from django.core.cache import cache
env = environ.Env()
environ.Env.read_env()
from ..models import Unit

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

async def get_exec_orcamen_last_teen_years():
    token = cache.get('token')
    exercicio = 2016
    url = FiplanAPI.BASE_URL + (f'/api/v1/execucao-orcamentaria/estatisticas-por-credor/'
                                f'?exercicio=${exercicio}$limitePorPagina=15$mesInicio=1&mesFim=$'
                                f'&unidadeOrcamentaria&codigoNaturezaDespesa=33903900')
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"
               }

    units = Unit.objects.all()

    while(exercicio < (exercicio + 10)):

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                return 'Erro em Buscar Unidades'