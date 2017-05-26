from django.contrib import admin

from endpoints.models import Request


class RequestAdmin(admin.ModelAdmin):
    search_fields = ('method', 'status', )
    list_display = ('method', 'status', 'created', 'filecount', )
    ordering = ('created', )

admin.site.register(Request, RequestAdmin)