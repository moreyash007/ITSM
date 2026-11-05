from django import forms
from .models import Asset
from users.models import User


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = [
            'name', 'asset_tag', 'asset_type', 'category', 'status',
            'manufacturer', 'model_number', 'serial_number', 'location',
            'department', 'assigned_to', 'purchase_date', 'warranty_expiry',
            'purchase_cost', 'ip_address', 'mac_address', 'os_version', 'notes'
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'warranty_expiry': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True)
