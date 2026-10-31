from django.contrib import admin

from portal.admin_utils import ImportedRecordAdmin

from .models import Contract, ContractDetail, ContractSnapshot


@admin.register(ContractSnapshot)
class ContractSnapshotAdmin(ImportedRecordAdmin):
    list_display = ('fiscal_year', 'updated_at')
    list_filter = ('fiscal_year',)
    ordering = ('-fiscal_year',)


@admin.register(Contract)
class ContractAdmin(ImportedRecordAdmin):
    list_display = ('fiscal_year', 'number', 'supplier_name', 'agency_name', 'contracted', 'paid', 'end')
    list_filter = ('fiscal_year',)
    search_fields = ('=contract_id', '=number', '=supplier_id')
    ordering = ('-fiscal_year', '-contract_id')


@admin.register(ContractDetail)
class ContractDetailAdmin(ImportedRecordAdmin):
    list_display = ('contract_id', 'fetched_at')
    search_fields = ('=contract_id',)
    ordering = ('-fetched_at',)
