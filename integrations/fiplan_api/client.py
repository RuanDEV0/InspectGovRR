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