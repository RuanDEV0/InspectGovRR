from ..repositories.unit_repository import UnitRepository

class UnitService:

    def __init__(self):
        self.unit_repository = UnitRepository()


    def _mapped_api_to_model(self, api_data, field_map):
        mapped = {}
        for api_field, model_field in field_map.items():
            mapped[model_field] = api_data.get(api_field)
        return mapped

    def save(self):
        pass