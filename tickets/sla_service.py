"""
sla_service.py — logic to attach SLA to tickets and check for breaches.
Called from ticket views and the check_sla management command.
"""
from django.utils import timezone
from datetime import timedelta


def attach_sla(ticket):
    """Create a TicketSLA record when a ticket is created."""
    from tickets.models import SLAPolicy, TicketSLA
    try:
        policy = SLAPolicy.objects.get(priority=ticket.priority)
    except SLAPolicy.DoesNotExist:
        return  # No SLA configured for this priority

    now = timezone.now()
    TicketSLA.objects.get_or_create(
        ticket=ticket,
        defaults=dict(
            policy=policy,
            response_due=now + timedelta(minutes=policy.response_time_minutes),
            resolution_due=now + timedelta(minutes=policy.resolution_time_minutes),
        )
    )


def check_sla_breaches():
    """
    Scan open tickets for SLA breaches.
    Sends email and marks breach flag. Safe to run repeatedly.
    Returns: count of newly breached tickets.
    """
    from tickets.models import TicketSLA, Ticket
    from itsm.notifications import notify_sla_breach, notify_sla_warning

    now = timezone.now()
    newly_breached = 0

    slas = TicketSLA.objects.select_related('ticket', 'ticket__assigned_to').filter(
        resolution_breached=False,
        ticket__status__in=['open', 'in_progress', 'pending'],
        resolution_due__lte=now,
    )

    for sla in slas:
        sla.resolution_breached = True
        if not sla.breach_notified:
            notify_sla_breach(sla.ticket)
            sla.breach_notified = True
        sla.save(update_fields=['resolution_breached', 'breach_notified'])
        newly_breached += 1

    # Early warning: SLA time elapsed has passed the policy's warning percentage
    open_slas = TicketSLA.objects.select_related('ticket', 'ticket__assigned_to', 'policy').filter(
        resolution_breached=False, warning_notified=False,
        ticket__status__in=['open', 'in_progress', 'pending'],
        policy__isnull=False,
    )
    for sla in open_slas:
        if sla.resolution_percent >= sla.policy.breach_warning_percent:
            notify_sla_warning(sla.ticket)
            sla.warning_notified = True
            sla.save(update_fields=['warning_notified'])

    return newly_breached


def record_first_response(ticket, responder):
    """Call when an agent first comments on a ticket."""
    from tickets.models import TicketSLA
    try:
        sla = ticket.sla
        if not sla.first_response_at and responder.is_agent:
            sla.first_response_at = timezone.now()
            if sla.first_response_at > sla.response_due:
                sla.response_breached = True
            sla.save(update_fields=['first_response_at', 'response_breached'])
    except TicketSLA.DoesNotExist:
        return  # ticket has no SLA (no policy for its priority)
