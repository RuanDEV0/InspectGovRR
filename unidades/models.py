from django.db import models


class Unit(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True, help_text='unit identifier code in the fiplan API')
    acronym = models.CharField(max_length=25, blank=True, null=True)

    class Meta:
        db_table = 'integrations_unit'

    def __str__(self):
        return f'{self.name} ({self.acronym})' if self.acronym else self.name
