from django.contrib import admin

from portal.admin_utils import ImportedRecordAdmin

from .models import CreditorSnapshot, Credor, Daily, SyncRun


@admin.register(Daily)
class LegacyDailyAdmin(ImportedRecordAdmin):
    exclude = ('recipient_cpf',)
    list_display = ('date_inicied', 'code_api', 'recipient_name', 'unit', 'value')
    list_filter = ('date_inicied',)
    search_fields = ('=code_api',)
    list_select_related = ('unit',)
    ordering = ('-date_inicied',)


@admin.register(Credor)
class CredorAdmin(ImportedRecordAdmin):
    list_display = ('name', 'cnpj', 'total_liquidado', 'total_pago', 'quantidade_pagamentos')
    search_fields = ('=cnpj',)
    ordering = ('name',)


@admin.register(CreditorSnapshot)
class CreditorSnapshotAdmin(ImportedRecordAdmin):
    exclude = ('identifier',)
    list_display = ('fiscal_year', 'unit', 'name', 'total_pago', 'quantidade_pagamentos', 'collected_at')
    list_filter = ('fiscal_year',)
    list_select_related = ('unit',)
    ordering = ('-fiscal_year', '-collected_at')


@admin.register(SyncRun)
class SyncRunAdmin(ImportedRecordAdmin):
    list_display = ('started_at', 'status', 'fiscal_year', 'nature_code', 'finished_at')
    list_filter = ('status', 'fiscal_year')
    ordering = ('-started_at',)
