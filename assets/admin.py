from django.contrib import admin
from .models import Asset, AssetCategory, AssetHistory

@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('asset_tag', 'name', 'asset_type', 'status', 'location', 'assigned_to')
    list_filter = ('status', 'asset_type', 'category')
    search_fields = ('name', 'asset_tag', 'serial_number')

admin.site.register(AssetHistory)
