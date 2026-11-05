from django.contrib import admin
from .models import Incident, IncidentUpdate

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('incident_id', 'title', 'severity', 'status', 'reported_by', 'created_at')
    list_filter = ('status', 'severity')
    search_fields = ('title', 'description')

admin.site.register(IncidentUpdate)
