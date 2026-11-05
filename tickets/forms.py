from django import forms
from .models import Ticket, TicketComment
from users.models import User


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'priority', 'category', 'due_date', 'attachment', 'status', 'assigned_to']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user and not self.user.is_agent:
            # End users can only set title, description, priority
            for field in ['status', 'assigned_to']:
                self.fields.pop(field, None)
        else:
            self.fields['assigned_to'].queryset = User.objects.filter(
                role__in=[User.Role.ADMIN, User.Role.AGENT], is_active=True
            )


class TicketCommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ['body', 'is_internal']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Add a comment...'}),
        }
        labels = {'is_internal': 'Internal note (agents only)'}


class TicketAssignForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['assigned_to']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(
            role__in=[User.Role.ADMIN, User.Role.AGENT], is_active=True
        )
