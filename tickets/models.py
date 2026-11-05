from django.db import models
from django.conf import settings
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Ticket(models.Model):
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In Progress'
        PENDING = 'pending', 'Pending'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED = 'closed', 'Closed'

    title = models.CharField(max_length=255)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='created_tickets', on_delete=models.CASCADE
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name='assigned_tickets', on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    attachment = models.FileField(upload_to='tickets/attachments/', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"TKT-{self.pk:04d}: {self.title}"

    @property
    def ticket_id(self):
        return f"TKT-{self.pk:04d}"

    def resolve(self):
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.save()

    @property
    def is_overdue(self):
        if self.due_date and self.status not in [self.Status.RESOLVED, self.Status.CLOSED]:
            return timezone.now() > self.due_date
        return False


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, related_name='comments', on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    is_internal = models.BooleanField(default=False, help_text='Internal notes visible only to agents')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author} on {self.ticket}"


class TicketHistory(models.Model):
    ticket = models.ForeignKey(Ticket, related_name='history', on_delete=models.CASCADE)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    field_changed = models.CharField(max_length=50)
    old_value = models.CharField(max_length=255, blank=True)
    new_value = models.CharField(max_length=255, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']


class SLAPolicy(models.Model):
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'

    priority = models.CharField(max_length=10, choices=Priority.choices, unique=True)
    response_time_minutes = models.PositiveIntegerField(default=480)
    resolution_time_minutes = models.PositiveIntegerField(default=1440)
    breach_warning_percent = models.PositiveIntegerField(default=80)

    class Meta:
        verbose_name = 'SLA Policy'
        verbose_name_plural = 'SLA Policies'

    def __str__(self):
        return f"SLA [{self.get_priority_display()}] — {self.resolution_time_minutes}min"


class TicketSLA(models.Model):
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='sla')
    policy = models.ForeignKey(SLAPolicy, on_delete=models.SET_NULL, null=True)
    response_due = models.DateTimeField()
    resolution_due = models.DateTimeField()
    first_response_at = models.DateTimeField(null=True, blank=True)
    response_breached = models.BooleanField(default=False)
    resolution_breached = models.BooleanField(default=False)
    breach_notified = models.BooleanField(default=False)
    warning_notified = models.BooleanField(default=False)

    def __str__(self):
        return f"SLA for {self.ticket.ticket_id}"

    @property
    def resolution_percent(self):
        if not self.policy:
            return 0
        elapsed = (timezone.now() - self.ticket.created_at).total_seconds() / 60
        return min(int((elapsed / self.policy.resolution_time_minutes) * 100), 999)

    @property
    def is_breached(self):
        return timezone.now() > self.resolution_due and \
               self.ticket.status not in ['resolved', 'closed']

    @property
    def time_remaining(self):
        delta = self.resolution_due - timezone.now()
        if delta.total_seconds() < 0:
            total = int(-delta.total_seconds())
            h, m = divmod(total, 3600)
            return f"BREACHED by {h}h {m//60}m"
        h, m = divmod(int(delta.total_seconds()), 3600)
        return f"{h}h {m//60}m remaining"
