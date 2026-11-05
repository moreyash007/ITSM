from django import forms
from .models import Incident, IncidentUpdate
from users.models import User


class IncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ['title', 'description', 'severity', 'status', 'assigned_to',
                  'affected_services', 'root_cause', 'resolution', 'related_ticket']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'root_cause': forms.Textarea(attrs={'rows': 3}),
            'resolution': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(
            role__in=[User.Role.ADMIN, User.Role.AGENT], is_active=True
        )


class IncidentUpdateForm(forms.ModelForm):
    new_status = forms.ChoiceField(
        choices=[('', '-- Keep current status --')] + Incident.Status.choices,
        required=False, label='Update Status To'
    )

    class Meta:
        model = IncidentUpdate
        fields = ['message', 'new_status']
        widgets = {'message': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe what changed or was found...'})}
