import requests
import httpx
import environ
import asyncio
from django.core.cache import cache
env = environ.Env()
environ.Env.read_env()

class FiplanAPI:
    BASE_URL = "https://api2.transparencia.rr.gov.br/transparencia"
    token = ''
    def __int__(self):
        self.token = asyncio.run(get_token())

    def get_units(self):
        url = self.BASE_URL + "/api/v1/unidades-orcamentarias/json"
        headers = {"Authorization": f"Bearer {self.token}",
                   "Content-Type": "application/json"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return "Erro em Buscar Unidades Orcamentarias"

    def get_dailies(self):
        url = self.BASE_URL + "/api/v1/diarias/json "

        headers = {"Authorization": f"Bearer {self.token}",
                   "Content-Type": "application/json"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return "Erro em Buscar Diarias"



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
