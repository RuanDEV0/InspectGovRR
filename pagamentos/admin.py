from django.contrib import admin

from .models import PaymentSnapshot


@admin.register(PaymentSnapshot)
class PaymentSnapshotAdmin(admin.ModelAdmin):
    list_display = ('year', 'month_end', 'status', 'record_count', 'total', 'finished_at')
    list_filter = ('year', 'status')
    readonly_fields = tuple(field.name for field in PaymentSnapshot._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
