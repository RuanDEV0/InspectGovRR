from django.db import models

class Unit(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True, help_text='unit identifier code in the fiplan API')
    acronym = models.CharField(max_length=25, blank=True, null=True)

    def __str__(self):
        return f'{self.name} ({self.acronym})' if self.acronym else self.name

class Daily(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='daily_units')
    code_api = models.CharField(max_length=50, unique=True)

    recipient_name = models.CharField(max_length=100)
    recipient_cpf = models.CharField(max_length=20, blank=True, null=True)
    position  = models.CharField(max_length=50, blank=True, null=True)

    date_inicied = models.DateField()
    date_return = models.DateField()
    value = models.DecimalField(decimal_places=2, max_digits=12, help_text="Valor total da diaria")

    reason = models.TextField(blank=True, null=True)
    destination = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['date_inicied']),
            models.Index(fields=['unit']),
        ]

    def __str__(self):
        return f"{self.date_inicied} - {self.recipient_name} - {self.value}"