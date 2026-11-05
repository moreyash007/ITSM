from django.contrib import admin
from .models import Ticket, TicketComment, TicketHistory, Category

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'title', 'priority', 'status', 'created_by', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'category')
    search_fields = ('title', 'description')
    raw_id_fields = ('created_by', 'assigned_to')

@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'author', 'is_internal', 'created_at')

admin.site.register(TicketHistory)
