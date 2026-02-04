import asyncio

from ..repositories.daily_repository import DailyRepository
from ..fiplan_api.client import get_dailies
def _mapped_api_to_model(api_data, field_map):
    mapped = {}

    for api_field, model_field in field_map.items():
        mapped[model_field] = api_data.get(api_field)

    return mapped


class DailyService:
    def __init__(self):
        self.repository = DailyRepository()

    def save(self):
        fields_map = {
            "codUnidadeOrcamentaria": "unit",
            "codUnidadeOrcamentaria": "code_api",
            "nomeCredor": "recipient_name",
            "cpf": "recipient_cpf",
            "cargo": "position",
            "dataInicio": "date_inicied",
            "dataRetorno": "date_return",
            "valor": "value",
            "motivo": "reason",
            "localidade": "destination"

        }

        dailies = asyncio.run(get_dailies())

        for daily in dailies:
            data = _mapped_api_to_model(daily, fields_map)
            self.repository.save(data)

    def get_dailies(self):
        data = self.repository.get_daily()
        return data['content']