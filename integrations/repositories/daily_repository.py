from ..models import Daily
from ..fiplan_api.client import FiplanAPI

class DailyRepository:

    def __init__(self):
        self.fiplan_api = FiplanAPI()

    def get_daily(self):
        # daily = Daily.objects.all()
        self.fiplan_api =  FiplanAPI()
        return self.fiplan_api.get_dailies()

    def save(self, data):
        Daily.objects.create(**data)