from ..repositories.daily_repository import DailyRepository

class DailyService:
    def __init__(self):
        self.repository = DailyRepository()

    def save(self, data):
        self.repository.save(data)

    def get_dailies(self):
        data = self.repository.get_daily()
        return data['content']