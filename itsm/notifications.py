"""
notifications.py — centralised email dispatch for ITSM events.
All sends are fire-and-forget; errors are logged, never raised.
"""
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _send(subject, template, context, recipient_list):
    """Internal helper — renders template and sends."""
    if not recipient_list:
        return
    try:
        html_message = render_to_string(template, context)
        plain_message = strip_tags(html_message)
        send_mail(
            subject=f"[ITSM] {subject}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info("Email sent: %s → %s", subject, recipient_list)
    except Exception as exc:
        logger.error("Email failed (%s): %s", subject, exc)


# ── Ticket notifications ────────────────────────────────────────────────────

def notify_ticket_created(ticket):
    recipients = []
    if ticket.assigned_to and ticket.assigned_to.email:
        recipients.append(ticket.assigned_to.email)
    _send(
        subject=f"New Ticket: {ticket.ticket_id} — {ticket.title}",
        template="emails/ticket_created.html",
        context={"ticket": ticket},
        recipient_list=recipients,
    )
    # Confirmation to requester
    if ticket.created_by.email:
        _send(
            subject=f"Your ticket {ticket.ticket_id} has been received",
            template="emails/ticket_created_requester.html",
            context={"ticket": ticket},
            recipient_list=[ticket.created_by.email],
        )


def notify_ticket_assigned(ticket, assigned_by):
    if not ticket.assigned_to or not ticket.assigned_to.email:
        return
    _send(
        subject=f"Ticket Assigned to You: {ticket.ticket_id} — {ticket.title}",
        template="emails/ticket_assigned.html",
        context={"ticket": ticket, "assigned_by": assigned_by},
        recipient_list=[ticket.assigned_to.email],
    )


def notify_ticket_resolved(ticket):
    if not ticket.created_by.email:
        return
    _send(
        subject=f"Your Ticket {ticket.ticket_id} Has Been Resolved",
        template="emails/ticket_resolved.html",
        context={"ticket": ticket},
        recipient_list=[ticket.created_by.email],
    )


def notify_ticket_comment(ticket, comment):
    recipients = set()
    if not comment.is_internal and ticket.created_by.email:
        recipients.add(ticket.created_by.email)
    if ticket.assigned_to and ticket.assigned_to.email and ticket.assigned_to != comment.author:
        recipients.add(ticket.assigned_to.email)
    recipients.discard(comment.author.email)
    _send(
        subject=f"New Comment on {ticket.ticket_id} — {ticket.title}",
        template="emails/ticket_comment.html",
        context={"ticket": ticket, "comment": comment},
        recipient_list=list(recipients),
    )


def notify_sla_breach(ticket):
    recipients = []
    if ticket.assigned_to and ticket.assigned_to.email:
        recipients.append(ticket.assigned_to.email)
    _send(
        subject=f"SLA BREACH: {ticket.ticket_id} — {ticket.title}",
        template="emails/sla_breach.html",
        context={"ticket": ticket},
        recipient_list=recipients,
    )


def notify_sla_warning(ticket):
    recipients = []
    if ticket.assigned_to and ticket.assigned_to.email:
        recipients.append(ticket.assigned_to.email)
    _send(
        subject=f"SLA WARNING: {ticket.ticket_id} — {ticket.title}",
        template="emails/sla_warning.html",
        context={"ticket": ticket},
        recipient_list=recipients,
    )


# ── Incident notifications ──────────────────────────────────────────────────

def notify_incident_created(incident):
    recipients = []
    if incident.assigned_to and incident.assigned_to.email:
        recipients.append(incident.assigned_to.email)
    _send(
        subject=f"[{incident.get_severity_display()}] Incident: {incident.incident_id} — {incident.title}",
        template="emails/incident_created.html",
        context={"incident": incident},
        recipient_list=recipients,
    )


def notify_incident_resolved(incident):
    recipients = []
    if incident.reported_by.email:
        recipients.append(incident.reported_by.email)
    _send(
        subject=f"Incident Resolved: {incident.incident_id} — {incident.title}",
        template="emails/incident_resolved.html",
        context={"incident": incident},
        recipient_list=recipients,
    )


# ── Change notifications ────────────────────────────────────────────────────

def notify_change_submitted(change):
    from users.models import User
    admins = User.objects.filter(role='admin', is_active=True).exclude(email='')
    recipients = list(admins.values_list('email', flat=True))
    _send(
        subject=f"Change Request Submitted: {change.change_id} — {change.title}",
        template="emails/change_submitted.html",
        context={"change": change},
        recipient_list=recipients,
    )


def notify_change_approved(change):
    if not change.requested_by.email:
        return
    _send(
        subject=f"Change Approved: {change.change_id} — {change.title}",
        template="emails/change_approved.html",
        context={"change": change},
        recipient_list=[change.requested_by.email],
    )


def notify_change_rejected(change):
    if not change.requested_by.email:
        return
    _send(
        subject=f"Change Rejected: {change.change_id} — {change.title}",
        template="emails/change_rejected.html",
        context={"change": change},
        recipient_list=[change.requested_by.email],
    )
