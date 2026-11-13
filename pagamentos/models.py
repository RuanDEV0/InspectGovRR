from django.db import models
from django.db.models import Q


class PaymentSnapshot(models.Model):
    class Status(models.TextChoices):
        LOADING = 'loading', 'Em coleta'
        PUBLISHED = 'published', 'Publicado'
        FAILED = 'failed', 'Falhou'
        REPLACED = 'replaced', 'Substituído'

    year = models.PositiveSmallIntegerField()
    month_end = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.LOADING)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    record_count = models.PositiveIntegerField(default=0)
    total = models.DecimalField(max_digits=22, decimal_places=2, null=True)
    failure_stage = models.CharField(max_length=40, blank=True)
    failure_type = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ('-year', '-id')
        constraints = [
            models.UniqueConstraint(
                fields=('year',), condition=Q(status='published'), name='payment_year_published_once',
            ),
            models.UniqueConstraint(
                fields=('year',), condition=Q(status='loading'), name='payment_year_loading_once',
            ),
            models.CheckConstraint(
                condition=Q(month_end__gte=1, month_end__lte=12), name='payment_snapshot_month_valid',
            ),
        ]


class Payment(models.Model):
    snapshot = models.ForeignKey(PaymentSnapshot, on_delete=models.CASCADE, related_name='payments')
    paid_on = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    unit_code = models.CharField(max_length=20)
    unit_name = models.CharField(max_length=255)
    nature_code = models.CharField(max_length=20, blank=True)
    nature_name = models.CharField(max_length=255, blank=True)
    expense_type = models.CharField(max_length=255, blank=True)
    creditor_kind = models.CharField(max_length=12, blank=True)
    creditor_name = models.CharField(max_length=255, blank=True)
    number = models.CharField(max_length=24)
    commitment = models.CharField(max_length=24, blank=True)
    settlement = models.CharField(max_length=24, blank=True)
    process = models.CharField(max_length=40, blank=True)
    process_url = models.URLField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('snapshot', 'unit_code', 'number'), name='payment_document_in_snapshot',
            ),
        ]
        indexes = [
            models.Index(fields=('snapshot', '-paid_on', '-id'), name='payment_snapshot_date_idx'),
            models.Index(fields=('snapshot', 'unit_code', '-paid_on'), name='payment_snapshot_unit_idx'),
            models.Index(fields=('snapshot', 'nature_code'), name='payment_snapshot_nature_idx'),
        ]
