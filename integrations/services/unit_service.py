from datetime import datetime
from sqlite3 import IntegrityError

from ..repositories.unit_repository import UnitRepository
from ..fiplan_api.client import FiplanAPI

def _mapped_api_to_model(api_data, field_map):
    mapped = {}
    for api_field, model_field in field_map.items():
        mapped[model_field] = api_data.get(api_field)
    return mapped


class UnitService:

    def __init__(self):
        self.unit_repository = UnitRepository()
        self.fiplan_api = FiplanAPI()

    def save(self):

        fields_map = {
            "codigoUnidadeorcamentaria": "code",
            "descricaoUnidadeOrcamentaria": "name",
            "sigla": "acronym",
        }

        units = self.fiplan_api.get_units()

        for unit in units:
            data = _mapped_api_to_model(unit, fields_map)
            self.unit_repository.save(data)


    def get_units(self):
        try:
            return self.unit_repository.get_units()
        except IntegrityError as ie:
            print(f"{datetime.now()} - DEBUG: {ie.__cause__}")
        except Exception as e:
            print(f"{datetime.now()} - DEBUG: {e.__cause__}")