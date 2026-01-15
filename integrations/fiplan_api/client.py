import requests
import environ

env = environ.Env()
environ.Env.read_env()

class FiplanAPI:
    BASE_URL = "https://api2.transparencia.rr.gov.br/transparencia"

    def __int__(self):
        self.token = self.get_token()

    def get_token(self) -> str:
        url = self.BASE_URL + "/oauth/token?grant_type=client_credentials"
        api_username = env("FIPLAN_USERNAME")
        api_password = env("FIPLAN_PASSWORD")

        response = requests.post(url, auth=(api_username, api_password), timeout=10)
        response.raise_for_status()

        data = response.json()
        return data["access_token"]

    def get_units(self):
        url = self.BASE_URL + "/api/v1/unidades-orcamentarias"
        headers = {"Authorization": f"Bearer {self.get_token()}",
                   "Content-Type": "application/json"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return "Erro em Buscar Unidades Orcamentarias"

    def get_dailies(self):
        url = self.BASE_URL + "api/v1/diarias"

        headers = {"Authorization": f"Bearer {self.get_token()}",
                   "Content-Type": "application/json"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        if(response.status_code == 200):
            data = response.json()
            return data
        else:
            return "Erro em Buscar Diarias"