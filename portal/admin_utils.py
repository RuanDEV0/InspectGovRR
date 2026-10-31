from django.contrib import admin


class ImportedRecordAdmin(admin.ModelAdmin):
    """Consulta administrativa sem alterar registros publicados pela sincronização."""

    list_per_page = 50
    show_full_result_count = False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
