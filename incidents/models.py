from django.db import models
from django.conf import settings
from django.utils import timezone


class Incident(models.Model):
    class Severity(models.TextChoices):
        SEV1 = 'sev1', 'SEV1 - Critical'
        SEV2 = 'sev2', 'SEV2 - High'
        SEV3 = 'sev3', 'SEV3 - Medium'
        SEV4 = 'sev4', 'SEV4 - Low'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        INVESTIGATING = 'investigating', 'Investigating'
        IDENTIFIED = 'identified', 'Identified'
        MONITORING = 'monitoring', 'Monitoring'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED = 'closed', 'Closed'

    title = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.SEV3)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='reported_incidents', on_delete=models.CASCADE
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name='assigned_incidents', on_delete=models.SET_NULL
    )
    affected_services = models.CharField(max_length=500, blank=True, help_text='Comma-separated list of affected services')
    root_cause = models.TextField(blank=True)
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    related_ticket = models.ForeignKey(
        'tickets.Ticket', null=True, blank=True, on_delete=models.SET_NULL, related_name='incidents'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"INC-{self.pk:04d}: {self.title}"

    @property
    def incident_id(self):
        return f"INC-{self.pk:04d}"

    def resolve(self, resolution_text=''):
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        if resolution_text:
            self.resolution = resolution_text
        self.save()

    @property
    def duration(self):
        end = self.resolved_at or timezone.now()
        delta = end - self.created_at
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m"


class IncidentUpdate(models.Model):
    incident = models.ForeignKey(Incident, related_name='updates', on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    status_at_time = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
