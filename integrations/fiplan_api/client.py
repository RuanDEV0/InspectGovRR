"""Cliente HTTP da API Fiplan, sem dependência dos modelos do portal."""

import os

import httpx
from django.conf import settings


class FiplanClient:
    BASE_URL = 'https://api2.transparencia.rr.gov.br/transparencia'

    def __init__(self, username=None, password=None, transport=None):
        self.username = username if username is not None else os.environ.get('FIPLAN_USERNAME', settings.FIPLAN_USERNAME)
        self.password = password if password is not None else os.environ.get('FIPLAN_PASSWORD', settings.FIPLAN_PASSWORD)
        if not self.username or not self.password:
            raise ValueError('Configure FIPLAN_USERNAME e FIPLAN_PASSWORD no .env')
        self.http = httpx.Client(timeout=60.0, transport=transport)
        self._token = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.http.close()

    def get_token(self):
        response = self.http.post(
            f'{self.BASE_URL}/oauth/token',
            params={'grant_type': 'client_credentials'},
            auth=(self.username, self.password),
        )
        response.raise_for_status()
        token = response.json().get('access_token')
        if not token:
            raise ValueError('A API Fiplan não retornou access_token')
        self._token = token
        return token

    def _get(self, path, params=None):
        if self._token is None:
            self.get_token()
        url = f'{self.BASE_URL}{path}'
        response = self.http.get(url, params=params, headers={'Authorization': f'Bearer {self._token}'})
        if response.status_code == 401:
            self.get_token()
            response = self.http.get(url, params=params, headers={'Authorization': f'Bearer {self._token}'})
        response.raise_for_status()
        return response.json()

    def get_units(self):
        return self._get('/api/v1/unidades-orcamentarias')

    def get_dailies(self):
        return self._get('/api/v1/diarias/json')

    def get_creditor_stats(self, unit_code, fiscal_year, nature_code, page=1, page_size=50):
        return self._get(
            '/api/v1/execucao-orcamentaria/estatisticas-por-credor/',
            params={
                'exercicio': fiscal_year,
                'limitePorPagina': page_size,
                'pagina': page,
                'mesInicio': 1,
                'mesFim': 12,
                'unidadeOrcamentaria': unit_code,
                'codigoNaturezaDespesa': nature_code,
            },
        )
