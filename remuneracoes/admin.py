from django.contrib import admin

from portal.admin_utils import ImportedRecordAdmin

from .models import PayrollSnapshot


@admin.register(PayrollSnapshot)
class PayrollSnapshotAdmin(ImportedRecordAdmin):
    list_display = ('year', 'month', 'updated_at')
    list_filter = ('year', 'month')
    ordering = ('-year', '-month')
