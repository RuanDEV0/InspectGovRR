from django.contrib import admin
from .models import Daily, Credor, CreditorSnapshot, SyncRun

admin.site.register(Daily)
admin.site.register(Credor)
admin.site.register(CreditorSnapshot)
admin.site.register(SyncRun)
