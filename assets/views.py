from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_POST
from .models import Asset, AssetCategory, AssetHistory
from .forms import AssetForm
from users.decorators import agent_required


@login_required
def asset_list(request):
    qs = Asset.objects.select_related('category', 'assigned_to')
    status = request.GET.get('status')
    asset_type = request.GET.get('type')
    search = request.GET.get('q')

    if status:
        qs = qs.filter(status=status)
    if asset_type:
        qs = qs.filter(asset_type=asset_type)
    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(asset_tag__icontains=search) |
            Q(serial_number__icontains=search) |
            Q(manufacturer__icontains=search)
        )

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'assets/asset_list.html', {
        'page_obj': page,
        'status_choices': Asset.Status.choices,
        'type_choices': Asset.AssetType.choices,
        'current_status': status,
        'current_type': asset_type,
        'search': search,
        'total_assets': Asset.objects.count(),
        'in_use': Asset.objects.filter(status='in_use').count(),
        'available': Asset.objects.filter(status='available').count(),
        'maintenance': Asset.objects.filter(status='maintenance').count(),
    })


@login_required
def asset_detail(request, pk):
    asset = get_object_or_404(Asset.objects.select_related('category', 'assigned_to'), pk=pk)
    return render(request, 'assets/asset_detail.html', {
        'asset': asset,
        'history': asset.history.select_related('changed_by'),
    })


@agent_required
def asset_create(request):
    form = AssetForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        asset = form.save()
        AssetHistory.objects.create(
            asset=asset, changed_by=request.user,
            action='Created', details=f'Asset {asset.asset_tag} added to CMDB'
        )
        messages.success(request, f'Asset {asset.asset_tag} created.')
        return redirect('assets:detail', pk=asset.pk)
    return render(request, 'assets/asset_form.html', {'form': form, 'title': 'Add Asset'})


@agent_required
def asset_edit(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    old_status = asset.status
    old_assigned = asset.assigned_to

    form = AssetForm(request.POST or None, instance=asset)
    if request.method == 'POST' and form.is_valid():
        updated = form.save()
        details = []
        if old_status != updated.status:
            details.append(f"Status: {old_status} → {updated.status}")
        if old_assigned != updated.assigned_to:
            details.append(f"Assigned: {old_assigned} → {updated.assigned_to}")
        if details:
            AssetHistory.objects.create(
                asset=updated, changed_by=request.user,
                action='Updated', details='; '.join(details)
            )
        messages.success(request, 'Asset updated.')
        return redirect('assets:detail', pk=pk)
    return render(request, 'assets/asset_form.html', {'form': form, 'title': f'Edit {asset.asset_tag}'})


@require_POST
@agent_required
def asset_retire(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    asset.status = Asset.Status.RETIRED
    asset.assigned_to = None
    asset.save()
    AssetHistory.objects.create(
        asset=asset, changed_by=request.user,
        action='Retired', details='Asset marked as retired'
    )
    messages.success(request, f'Asset {asset.asset_tag} retired.')
    return redirect('assets:detail', pk=pk)
