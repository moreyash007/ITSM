from django.db import models
from django.conf import settings


class AssetCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'asset categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Asset(models.Model):
    class Status(models.TextChoices):
        IN_USE = 'in_use', 'In Use'
        AVAILABLE = 'available', 'Available'
        MAINTENANCE = 'maintenance', 'Under Maintenance'
        RETIRED = 'retired', 'Retired'
        DISPOSED = 'disposed', 'Disposed'

    class AssetType(models.TextChoices):
        HARDWARE = 'hardware', 'Hardware'
        SOFTWARE = 'software', 'Software'
        NETWORK = 'network', 'Network'
        VIRTUAL = 'virtual', 'Virtual/Cloud'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=255)
    asset_tag = models.CharField(max_length=100, unique=True)
    asset_type = models.CharField(max_length=20, choices=AssetType.choices, default=AssetType.HARDWARE)
    category = models.ForeignKey(AssetCategory, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    manufacturer = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True, unique=True)
    location = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=100, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name='assigned_assets', on_delete=models.SET_NULL
    )
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=17, blank=True)
    os_version = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['asset_tag']

    def __str__(self):
        return f"{self.asset_tag}: {self.name}"


class AssetHistory(models.Model):
    asset = models.ForeignKey(Asset, related_name='history', on_delete=models.CASCADE)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    details = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']
