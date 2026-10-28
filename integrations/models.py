from django.db import models

class Daily(models.Model):
    unit = models.ForeignKey('unidades.Unit', on_delete=models.CASCADE, related_name='daily_units')
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

class Credor(models.Model):
    # Dados anteriores à sincronização por período; mantidos para preservar registros.
    name = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=14)
    total_liquidado = models.DecimalField(max_digits=12, decimal_places=2)
    total_pago = models.DecimalField(max_digits=12, decimal_places=2)
    quantidade_pagamentos = models.IntegerField()

    def __str__(self):
        return f"{self.name} ({self.cnpj})"


class CreditorSnapshot(models.Model):
    run = models.ForeignKey('SyncRun', on_delete=models.CASCADE, related_name='creditor_snapshots')
    unit = models.ForeignKey('unidades.Unit', on_delete=models.CASCADE, related_name='creditor_snapshots')
    identifier = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    fiscal_year = models.PositiveSmallIntegerField()
    nature_code = models.CharField(max_length=20)
    month_start = models.PositiveSmallIntegerField(default=1)
    month_end = models.PositiveSmallIntegerField(default=12)
    total_liquidado = models.DecimalField(max_digits=16, decimal_places=2)
    total_pago = models.DecimalField(max_digits=16, decimal_places=2)
    quantidade_pagamentos = models.PositiveIntegerField()
    collected_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['run', 'unit', 'identifier'],
                name='unique_creditor_snapshot',
            ),
        ]
        indexes = [
            models.Index(fields=['fiscal_year', 'nature_code']),
        ]


class SyncRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = 'running', 'Em andamento'
        SUCCESS = 'success', 'Concluída'
        FAILED = 'failed', 'Falhou'

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    fiscal_year = models.PositiveSmallIntegerField()
    nature_code = models.CharField(max_length=20)
    counts = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']
