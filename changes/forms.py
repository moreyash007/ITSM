from django import forms
from .models import ChangeRequest, ChangeApproval
from users.models import User


class ChangeRequestForm(forms.ModelForm):
    class Meta:
        model = ChangeRequest
        fields = [
            'title', 'description', 'change_type', 'risk_level',
            'justification', 'implementation_plan', 'rollback_plan', 'test_plan',
            'scheduled_start', 'scheduled_end', 'assigned_to'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'justification': forms.Textarea(attrs={'rows': 3}),
            'implementation_plan': forms.Textarea(attrs={'rows': 4}),
            'rollback_plan': forms.Textarea(attrs={'rows': 3}),
            'test_plan': forms.Textarea(attrs={'rows': 3}),
            'scheduled_start': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'scheduled_end': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(
            role__in=[User.Role.ADMIN, User.Role.AGENT], is_active=True
        )


class ChangeApprovalForm(forms.ModelForm):
    class Meta:
        model = ChangeApproval
        fields = ['decision', 'comments']
        widgets = {'comments': forms.Textarea(attrs={'rows': 3})}
