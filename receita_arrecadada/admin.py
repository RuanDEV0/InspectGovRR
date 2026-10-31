from django.contrib import admin

from portal.admin_utils import ImportedRecordAdmin

from .models import RevenueSnapshot


@admin.register(RevenueSnapshot)
class RevenueSnapshotAdmin(ImportedRecordAdmin):
    list_display = ('fiscal_year', 'month_start', 'month_end', 'updated_at')
    list_filter = ('fiscal_year',)
    ordering = ('-fiscal_year', '-month_end', '-updated_at')
