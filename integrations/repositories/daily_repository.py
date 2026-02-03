from ..models import Daily
from ..fiplan_api.client import FiplanAPI

class DailyRepository:

    def __init__(self):
        self.fiplan_api = FiplanAPI()

    def get_daily(self):
        # daily = Daily.objects.all()
        data = self.fiplan_api.get_dailies()
        return data

    def save(self, data):
        Daily.objects.create(**data)