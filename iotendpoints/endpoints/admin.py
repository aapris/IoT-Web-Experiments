from django.contrib.gis import admin
from endpoints.models import Request, Datalogger


class RequestAdmin(admin.ModelAdmin):
    search_fields = ('method', 'status', 'user')
    list_display = ('method', 'status', 'user', 'created', 'filecount',)
    ordering = ('created',)


admin.site.register(Request, RequestAdmin)


class DataloggerAdmin(admin.OSMGeoAdmin):
    search_fields = ('name', 'description', 'devid')
    list_display = ('devid', 'activity_at', 'lat', 'lon', 'name', 'created_at',)
    ordering = ('created_at',)
    readonly_fields = ('location',)


admin.site.register(Datalogger, DataloggerAdmin)
