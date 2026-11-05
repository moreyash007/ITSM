from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Incident, IncidentUpdate
from .forms import IncidentForm, IncidentUpdateForm
from users.decorators import agent_required
from itsm.notifications import notify_incident_created, notify_incident_resolved


@login_required
def incident_list(request):
    qs = Incident.objects.select_related('reported_by', 'assigned_to')
    status = request.GET.get('status')
    severity = request.GET.get('severity')
    search = request.GET.get('q')

    if status:
        qs = qs.filter(status=status)
    if severity:
        qs = qs.filter(severity=severity)
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'incidents/incident_list.html', {
        'page_obj': page,
        'status_choices': Incident.Status.choices,
        'severity_choices': Incident.Severity.choices,
        'current_status': status,
        'current_severity': severity,
        'search': search,
    })


@login_required
def incident_detail(request, pk):
    incident = get_object_or_404(Incident.objects.select_related('reported_by', 'assigned_to'), pk=pk)
    update_form = IncidentUpdateForm(request.POST or None)
    if request.method == 'POST' and request.user.is_agent and update_form.is_valid():
        update = update_form.save(commit=False)
        update.incident = incident
        update.author = request.user
        update.status_at_time = incident.status

        new_status = update_form.cleaned_data.get('new_status')
        if new_status:
            if new_status == 'resolved':
                incident.resolve()
                notify_incident_resolved(incident)
            else:
                incident.status = new_status
                incident.save()

        update.save()
        messages.success(request, 'Incident updated.')
        return redirect('incidents:detail', pk=pk)

    return render(request, 'incidents/incident_detail.html', {
        'incident': incident,
        'updates': incident.updates.select_related('author'),
        'update_form': update_form,
    })


@agent_required
def incident_create(request):
    form = IncidentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        incident = form.save(commit=False)
        incident.reported_by = request.user
        incident.save()
        notify_incident_created(incident)
        IncidentUpdate.objects.create(
            incident=incident, author=request.user,
            message='Incident created.', status_at_time=incident.status
        )
        messages.success(request, f'{incident.incident_id} created.')
        return redirect('incidents:detail', pk=incident.pk)
    return render(request, 'incidents/incident_form.html', {'form': form, 'title': 'New Incident'})


@agent_required
def incident_edit(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    form = IncidentForm(request.POST or None, instance=incident)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Incident updated.')
        return redirect('incidents:detail', pk=pk)
    return render(request, 'incidents/incident_form.html', {
        'form': form, 'title': f'Edit {incident.incident_id}'
    })
