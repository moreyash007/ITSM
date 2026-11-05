from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Ticket, TicketComment, TicketHistory
from .forms import TicketForm, TicketCommentForm, TicketAssignForm
from users.decorators import agent_required
from itsm.notifications import (
    notify_ticket_created, notify_ticket_assigned,
    notify_ticket_resolved, notify_ticket_comment,
)
from .sla_service import attach_sla, record_first_response


def _log_change(ticket, user, field, old, new):
    if str(old) != str(new):
        TicketHistory.objects.create(
            ticket=ticket, changed_by=user,
            field_changed=field, old_value=str(old), new_value=str(new)
        )


@login_required
def ticket_list(request):
    qs = Ticket.objects.select_related('created_by', 'assigned_to', 'category')
    if not request.user.is_agent:
        qs = qs.filter(created_by=request.user)

    # Filters
    status = request.GET.get('status')
    priority = request.GET.get('priority')
    search = request.GET.get('q')
    assigned = request.GET.get('assigned')

    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))
    if assigned == 'me' and request.user.is_agent:
        qs = qs.filter(assigned_to=request.user)
    if assigned == 'unassigned' and request.user.is_agent:
        qs = qs.filter(assigned_to__isnull=True)

    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page,
        'status_choices': Ticket.Status.choices,
        'priority_choices': Ticket.Priority.choices,
        'current_status': status,
        'current_priority': priority,
        'search': search,
        'assigned': assigned,
        'stats': {
            'open': Ticket.objects.filter(status='open').count(),
            'in_progress': Ticket.objects.filter(status='in_progress').count(),
            'pending': Ticket.objects.filter(status='pending').count(),
            'resolved': Ticket.objects.filter(status='resolved').count(),
        }
    }
    return render(request, 'tickets/ticket_list.html', context)


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket.objects.select_related('created_by', 'assigned_to', 'category'), pk=pk)
    if not request.user.is_agent and ticket.created_by != request.user:
        messages.error(request, 'Access denied.')
        return redirect('tickets:list')

    comment_form = TicketCommentForm(request.POST or None)
    if request.method == 'POST' and comment_form.is_valid():
        comment = comment_form.save(commit=False)
        comment.ticket = ticket
        comment.author = request.user
        # Non-agents can't post internal notes
        if not request.user.is_agent:
            comment.is_internal = False
        comment.save()
        record_first_response(ticket, request.user)
        notify_ticket_comment(ticket, comment)
        messages.success(request, 'Comment added.')
        return redirect('tickets:detail', pk=pk)

    comments = ticket.comments.select_related('author')
    if not request.user.is_agent:
        comments = comments.filter(is_internal=False)

    return render(request, 'tickets/ticket_detail.html', {
        'ticket': ticket,
        'comment_form': comment_form,
        'comments': comments,
        'history': ticket.history.select_related('changed_by'),
    })


@login_required
def ticket_create(request):
    form = TicketForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        ticket = form.save(commit=False)
        ticket.created_by = request.user
        ticket.save()
        attach_sla(ticket)
        notify_ticket_created(ticket)
        messages.success(request, f'{ticket.ticket_id} created successfully.')
        return redirect('tickets:detail', pk=ticket.pk)
    return render(request, 'tickets/ticket_form.html', {'form': form, 'title': 'New Ticket'})


@agent_required
def ticket_edit(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    old_status = ticket.status
    old_priority = ticket.priority
    old_assigned = ticket.assigned_to

    form = TicketForm(request.POST or None, request.FILES or None, instance=ticket, user=request.user)
    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        if updated.status in (Ticket.Status.RESOLVED, Ticket.Status.CLOSED) and not updated.resolved_at:
            updated.resolved_at = timezone.now()
        elif updated.status not in (Ticket.Status.RESOLVED, Ticket.Status.CLOSED):
            updated.resolved_at = None
        updated.save()
        _log_change(updated, request.user, 'status', old_status, updated.status)
        _log_change(updated, request.user, 'priority', old_priority, updated.priority)
        _log_change(updated, request.user, 'assigned_to', old_assigned, updated.assigned_to)
        if updated.assigned_to and updated.assigned_to != old_assigned:
            notify_ticket_assigned(updated, request.user)
        messages.success(request, 'Ticket updated.')
        return redirect('tickets:detail', pk=pk)
    return render(request, 'tickets/ticket_form.html', {'form': form, 'title': f'Edit {ticket.ticket_id}'})


@require_POST
@agent_required
def ticket_resolve(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    old_status = ticket.status
    ticket.resolve()
    _log_change(ticket, request.user, 'status', old_status, ticket.status)
    notify_ticket_resolved(ticket)
    messages.success(request, f'{ticket.ticket_id} marked as resolved.')
    return redirect('tickets:detail', pk=pk)


@require_POST
@agent_required
def ticket_close(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    old_status = ticket.status
    ticket.status = Ticket.Status.CLOSED
    ticket.save()
    _log_change(ticket, request.user, 'status', old_status, ticket.status)
    messages.success(request, f'{ticket.ticket_id} closed.')
    return redirect('tickets:detail', pk=pk)
