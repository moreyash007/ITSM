from django.contrib import admin
from .models import ChangeRequest, ChangeApproval

@admin.register(ChangeRequest)
class ChangeRequestAdmin(admin.ModelAdmin):
    list_display = ('change_id', 'title', 'change_type', 'risk_level', 'status', 'requested_by', 'created_at')
    list_filter = ('status', 'change_type', 'risk_level')
    search_fields = ('title', 'description')

admin.site.register(ChangeApproval)
