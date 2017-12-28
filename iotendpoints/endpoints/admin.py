from django.contrib import admin

from endpoints.models import Request


class RequestAdmin(admin.ModelAdmin):
    search_fields = ('method', 'status', 'user')
    list_display = ('method', 'status', 'user', 'created', 'filecount', )
    ordering = ('created', )

admin.site.register(Request, RequestAdmin)
