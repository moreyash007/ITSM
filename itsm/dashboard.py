from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from tickets.models import Ticket, TicketSLA
from incidents.models import Incident
from changes.models import ChangeRequest
from assets.models import Asset
from users.models import User


@login_required
def dashboard(request):
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    # ── Ticket stats ───────────────────────────────────────
    ticket_qs = Ticket.objects.all()
    if not request.user.is_agent:
        ticket_qs = ticket_qs.filter(created_by=request.user)

    ticket_by_status = dict(
        ticket_qs.values_list('status').annotate(c=Count('id')).values_list('status', 'c')
    )
    ticket_by_priority = dict(
        ticket_qs.values_list('priority').annotate(c=Count('id')).values_list('priority', 'c')
    )

    # Ticket volume last 30 days (daily)
    daily_tickets = []
    for i in range(29, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = ticket_qs.filter(created_at__gte=day_start, created_at__lt=day_end).count()
        daily_tickets.append({'date': day_start.strftime('%d %b'), 'count': count})

    # ── SLA stats ──────────────────────────────────────────
    sla_breached = TicketSLA.objects.filter(
        resolution_breached=True,
        ticket__created_at__gte=thirty_days_ago
    ).count()
    sla_total = TicketSLA.objects.filter(ticket__created_at__gte=thirty_days_ago).count()
    sla_compliance = round((1 - sla_breached / sla_total) * 100, 1) if sla_total > 0 else 100

    # ── Incident stats ─────────────────────────────────────
    open_incidents = Incident.objects.exclude(status__in=['resolved', 'closed'])
    incident_by_severity = dict(
        Incident.objects.filter(created_at__gte=thirty_days_ago)
        .values_list('severity').annotate(c=Count('id')).values_list('severity', 'c')
    )

    # Average resolution time (minutes) for resolved incidents last 30d
    avg_inc_resolution = None
    resolved_incs = Incident.objects.filter(
        status='resolved', resolved_at__isnull=False, created_at__gte=thirty_days_ago
    )
    if resolved_incs.exists():
        total_mins = sum(
            (i.resolved_at - i.created_at).total_seconds() / 60
            for i in resolved_incs
        )
        avg_mins = total_mins / resolved_incs.count()
        avg_inc_resolution = f"{int(avg_mins // 60)}h {int(avg_mins % 60)}m"

    # ── Change stats ───────────────────────────────────────
    change_by_status = dict(
        ChangeRequest.objects.values_list('status').annotate(c=Count('id')).values_list('status', 'c')
    )

    # ── Asset stats ────────────────────────────────────────
    asset_by_status = dict(
        Asset.objects.values_list('status').annotate(c=Count('id')).values_list('status', 'c')
    )

    # ── Agent leaderboard (last 7d resolved tickets) ───────
    leaderboard = []
    if request.user.is_agent:
        leaderboard = (
            User.objects.filter(
                role__in=['admin', 'agent'],
                assigned_tickets__status='resolved',
                assigned_tickets__resolved_at__gte=seven_days_ago
            )
            .annotate(resolved_count=Count('assigned_tickets'))
            .order_by('-resolved_count')[:5]
        )

    # ── Recent items ───────────────────────────────────────
    recent_tickets = ticket_qs.select_related('created_by', 'assigned_to').order_by('-created_at')[:5]
    recent_incidents = Incident.objects.exclude(status='closed').order_by('-created_at')[:5]

    context = {
        # Tickets
        'total_tickets': ticket_qs.count(),
        'open_tickets': ticket_by_status.get('open', 0),
        'in_progress_tickets': ticket_by_status.get('in_progress', 0),
        'resolved_tickets': ticket_by_status.get('resolved', 0),
        'ticket_by_status': ticket_by_status,
        'ticket_by_priority': ticket_by_priority,
        'daily_tickets': daily_tickets,
        # SLA
        'sla_compliance': sla_compliance,
        'sla_breached': sla_breached,
        # Incidents
        'open_incidents_count': open_incidents.count(),
        'incident_by_severity': incident_by_severity,
        'avg_inc_resolution': avg_inc_resolution,
        # Changes
        'pending_changes': ChangeRequest.objects.filter(
            status__in=['submitted', 'under_review']
        ).count(),
        'change_by_status': change_by_status,
        # Assets
        'total_assets': Asset.objects.count(),
        'asset_by_status': asset_by_status,
        # People
        'leaderboard': leaderboard,
        # Recent
        'recent_tickets': recent_tickets,
        'recent_incidents': recent_incidents,
    }
    return render(request, 'dashboard/dashboard.html', context)
