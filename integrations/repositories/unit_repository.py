from ..models import Unit


class UnitRepository:

    def __init__(self):
        pass

    def save(self, data):
        Unit.objects.create(**data)

    def get_units(self):
        units = Unit.objects.all()
        return units