from django.contrib import admin

from portal.admin_utils import ImportedRecordAdmin

from .models import DailySnapshot, DailyTrip


@admin.register(DailySnapshot)
class DailySnapshotAdmin(ImportedRecordAdmin):
    list_display = ('year', 'source_count', 'updated_at')
    list_filter = ('year',)
    ordering = ('-year',)


@admin.register(DailyTrip)
class DailyTripAdmin(ImportedRecordAdmin):
    list_display = ('year', 'commitment', 'name', 'agency', 'start', 'paid', 'status')
    list_filter = ('year', 'status')
    search_fields = ('=commitment',)
    ordering = ('-year', '-start', 'id')
