from django.db import models


class RevenueSnapshot(models.Model):
    fiscal_year = models.PositiveSmallIntegerField()
    month_start = models.PositiveSmallIntegerField()
    month_end = models.PositiveSmallIntegerField()
    rows = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['fiscal_year', 'month_start', 'month_end'],
                name='unique_revenue_snapshot_period',
            ),
        ]
        ordering = ['-fiscal_year', '-month_end', '-updated_at']

    def __str__(self):
        return f'Receita arrecadada: {self.month_start}-{self.month_end}/{self.fiscal_year}'
