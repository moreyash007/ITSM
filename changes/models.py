from django.db import models
from django.conf import settings


class ChangeRequest(models.Model):
    class Type(models.TextChoices):
        STANDARD = 'standard', 'Standard'
        NORMAL = 'normal', 'Normal'
        EMERGENCY = 'emergency', 'Emergency'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        UNDER_REVIEW = 'under_review', 'Under Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        IMPLEMENTING = 'implementing', 'Implementing'
        IMPLEMENTED = 'implemented', 'Implemented'
        CLOSED = 'closed', 'Closed'
        CANCELLED = 'cancelled', 'Cancelled'

    class Risk(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        VERY_HIGH = 'very_high', 'Very High'

    title = models.CharField(max_length=255)
    description = models.TextField()
    change_type = models.CharField(max_length=20, choices=Type.choices, default=Type.NORMAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    risk_level = models.CharField(max_length=10, choices=Risk.choices, default=Risk.MEDIUM)
    justification = models.TextField(help_text='Why this change is needed')
    implementation_plan = models.TextField(help_text='Step-by-step implementation plan')
    rollback_plan = models.TextField(help_text='How to revert if something goes wrong')
    test_plan = models.TextField(blank=True, help_text='Testing steps to validate change')
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='requested_changes', on_delete=models.CASCADE
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name='implementing_changes', on_delete=models.SET_NULL
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name='approved_changes', on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    implemented_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"CHG-{self.pk:04d}: {self.title}"

    @property
    def change_id(self):
        return f"CHG-{self.pk:04d}"


class ChangeApproval(models.Model):
    class Decision(models.TextChoices):
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        ABSTAINED = 'abstained', 'Abstained'

    change = models.ForeignKey(ChangeRequest, related_name='approvals', on_delete=models.CASCADE)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    decision = models.CharField(max_length=20, choices=Decision.choices)
    comments = models.TextField(blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('change', 'approver')
