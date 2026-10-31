from django.db import models


class DailySnapshot(models.Model):
    year = models.PositiveSmallIntegerField(unique=True)
    summary = models.JSONField(default=dict)
    source_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year']

    def __str__(self):
        return f'Diárias de {self.year}'


class DailyTrip(models.Model):
    """Uma pessoa em um deslocamento; substituído por inteiro a cada coleta do ano."""

    class Status(models.TextChoices):
        PAID = 'paid', 'Pago'
        PENDING = 'pending', 'Sem pagamento registrado'
        REVERSED = 'reversed', 'Estornado'

    year = models.PositiveSmallIntegerField()
    commitment = models.CharField(max_length=30, help_text='numeroEmpenho, único por viagem na fonte')
    person_id = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, blank=True)
    unit = models.CharField(max_length=10)
    agency = models.CharField(max_length=255, blank=True)
    acronym = models.CharField(max_length=30, blank=True)
    start = models.DateField(null=True)
    end = models.DateField(null=True)
    destination = models.TextField(blank=True)
    scope = models.CharField(max_length=2)
    places = models.JSONField(default=list, help_text='Lugares identificados pelo portal no texto de destino')
    reason = models.TextField(blank=True)
    theme = models.CharField(max_length=30)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    daily_value = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    formula_ok = models.BooleanField(default=False)
    committed = models.DecimalField(max_digits=16, decimal_places=2, null=True)
    paid = models.DecimalField(max_digits=16, decimal_places=2)
    reversed = models.DecimalField(max_digits=16, decimal_places=2, null=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    process = models.CharField(max_length=40, blank=True)
    sei_url = models.URLField(max_length=300, blank=True)

    class Meta:
        ordering = ['-start', 'id']
        constraints = [
            models.UniqueConstraint(fields=['year', 'commitment'], name='unique_daily_commitment_per_year'),
        ]
        indexes = [
            models.Index(fields=['year', 'person_id']),
            models.Index(fields=['year', 'acronym']),
            models.Index(fields=['year', 'theme']),
            models.Index(fields=['year', 'scope']),
        ]

    def __str__(self):
        return f'{self.commitment} · {self.destination[:40]}'
