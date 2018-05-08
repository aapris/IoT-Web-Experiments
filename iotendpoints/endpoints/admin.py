from django.contrib.gis import admin
from endpoints.models import Request, Datalogger


class RequestAdmin(admin.ModelAdmin):
    search_fields = ('method', 'status', 'user')
    list_display = ('method', 'status', 'user', 'created', 'filecount',)
    ordering = ('created',)


admin.site.register(Request, RequestAdmin)


class DataloggerAdmin(admin.OSMGeoAdmin):
    search_fields = ('name', 'description', 'devid')
    list_display = ('devid', 'location', 'name', 'created_at', 'activity_at',)
    ordering = ('created_at',)

admin.site.register(Datalogger, DataloggerAdmin)
