from django.db import models


class ContractSnapshot(models.Model):
    fiscal_year = models.PositiveSmallIntegerField(unique=True)
    summary = models.JSONField(default=dict)
    agencies = models.JSONField(default=list)
    suppliers = models.JSONField(default=list)
    history = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fiscal_year']

    def __str__(self):
        return f'Contratos com vigência em {self.fiscal_year}'


class Contract(models.Model):
    """Contrato do snapshot; substituído por inteiro a cada coleta do ano."""

    fiscal_year = models.PositiveSmallIntegerField()
    contract_id = models.PositiveBigIntegerField()
    supplier_id = models.CharField(max_length=16)
    supplier_name = models.CharField(max_length=255)
    agency_code = models.CharField(max_length=10)
    agency_name = models.CharField(max_length=255)
    number = models.CharField(max_length=20)
    subject = models.TextField(blank=True)
    kind = models.CharField(max_length=100, blank=True)
    situation = models.CharField(max_length=30, blank=True)
    signed_at = models.DateField(null=True)
    start = models.DateField(null=True)
    end = models.DateField(null=True, help_text='Fim da vigência, já com prorrogações')
    original_end = models.DateField(null=True)
    original = models.DecimalField(max_digits=16, decimal_places=2, null=True)
    contracted = models.DecimalField(max_digits=16, decimal_places=2)
    additives = models.DecimalField(max_digits=16, decimal_places=2)
    liquidated = models.DecimalField(max_digits=16, decimal_places=2)
    paid = models.DecimalField(max_digits=16, decimal_places=2)
    sei_number = models.CharField(max_length=40, blank=True)
    sei_url = models.URLField(max_length=300, blank=True)
    has_changes = models.BooleanField(default=False)
    signature = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['fiscal_year', 'contract_id'], name='unique_contract_per_year'),
        ]
        indexes = [
            models.Index(fields=['fiscal_year', 'supplier_id']),
            models.Index(fields=['fiscal_year', 'end']),
        ]

    def __str__(self):
        return f'{self.number} · {self.supplier_name}'


class ContractDetail(models.Model):
    """Aditivos e fiscais de um contrato, coletados aos poucos e mantidos entre coletas."""

    contract_id = models.PositiveBigIntegerField(primary_key=True)
    signature = models.CharField(max_length=120)
    additives = models.JSONField(default=list)
    inspectors = models.JSONField(default=list)
    fetched_at = models.DateTimeField()

    def __str__(self):
        return f'Detalhes do contrato {self.contract_id}'
