from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import ChangeRequest, ChangeApproval
from .forms import ChangeRequestForm, ChangeApprovalForm
from users.decorators import agent_required, admin_required
from itsm.notifications import notify_change_submitted, notify_change_approved, notify_change_rejected


@login_required
def change_list(request):
    qs = ChangeRequest.objects.select_related('requested_by', 'assigned_to')
    if not request.user.is_agent:
        qs = qs.filter(requested_by=request.user)

    status = request.GET.get('status')
    change_type = request.GET.get('type')
    if status:
        qs = qs.filter(status=status)
    if change_type:
        qs = qs.filter(change_type=change_type)

    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'changes/change_list.html', {
        'page_obj': page,
        'status_choices': ChangeRequest.Status.choices,
        'type_choices': ChangeRequest.Type.choices,
        'current_status': status,
        'current_type': change_type,
    })


@login_required
def change_detail(request, pk):
    change = get_object_or_404(ChangeRequest.objects.select_related('requested_by', 'assigned_to', 'approved_by'), pk=pk)
    if not request.user.is_agent and change.requested_by != request.user:
        messages.error(request, 'Access denied.')
        return redirect('changes:list')
    approval_form = None
    user_approval = None

    if request.user.is_admin_role and change.status in [ChangeRequest.Status.SUBMITTED, ChangeRequest.Status.UNDER_REVIEW]:
        user_approval = ChangeApproval.objects.filter(change=change, approver=request.user).first()
        if not user_approval:
            approval_form = ChangeApprovalForm(request.POST or None)
            if request.method == 'POST' and approval_form.is_valid():
                approval = approval_form.save(commit=False)
                approval.change = change
                approval.approver = request.user
                approval.save()
                if approval.decision == ChangeApproval.Decision.APPROVED:
                    change.status = ChangeRequest.Status.APPROVED
                    change.approved_by = request.user
                    change.approved_at = timezone.now()
                    change.save()
                    notify_change_approved(change)
                elif approval.decision == ChangeApproval.Decision.REJECTED:
                    change.status = ChangeRequest.Status.REJECTED
                    change.save()
                    notify_change_rejected(change)
                messages.success(request, f'Decision recorded: {approval.get_decision_display()}')
                return redirect('changes:detail', pk=pk)

    return render(request, 'changes/change_detail.html', {
        'change': change,
        'approvals': change.approvals.select_related('approver'),
        'approval_form': approval_form,
        'user_approval': user_approval,
    })


@login_required
def change_create(request):
    form = ChangeRequestForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        change = form.save(commit=False)
        change.requested_by = request.user
        change.save()
        messages.success(request, f'{change.change_id} created.')
        return redirect('changes:detail', pk=change.pk)
    return render(request, 'changes/change_form.html', {'form': form, 'title': 'New Change Request'})


@login_required
def change_edit(request, pk):
    change = get_object_or_404(ChangeRequest, pk=pk)
    if not request.user.is_admin_role and change.requested_by != request.user:
        messages.error(request, 'Access denied.')
        return redirect('changes:list')
    if change.status not in [ChangeRequest.Status.DRAFT] and not request.user.is_admin_role:
        messages.error(request, 'Only draft changes can be edited.')
        return redirect('changes:detail', pk=pk)

    form = ChangeRequestForm(request.POST or None, instance=change, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Change request updated.')
        return redirect('changes:detail', pk=pk)
    return render(request, 'changes/change_form.html', {'form': form, 'title': f'Edit {change.change_id}'})


@require_POST
@login_required
def change_submit(request, pk):
    change = get_object_or_404(ChangeRequest, pk=pk, requested_by=request.user)
    if change.status == ChangeRequest.Status.DRAFT:
        change.status = ChangeRequest.Status.SUBMITTED
        change.save()
        notify_change_submitted(change)
        messages.success(request, f'{change.change_id} submitted for review.')
    return redirect('changes:detail', pk=pk)
