from django.db import models


class PayrollSnapshot(models.Model):
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    rows = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(fields=['year', 'month'], name='unique_payroll_period'),
            models.CheckConstraint(condition=models.Q(month__gte=1, month__lte=12), name='valid_payroll_month'),
        ]

    def __str__(self):
        return f'Remunerações: {self.month:02d}/{self.year}'
