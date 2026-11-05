from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from tickets.models import Ticket, TicketComment, Category, TicketSLA
from incidents.models import Incident, IncidentUpdate
from changes.models import ChangeRequest, ChangeApproval
from assets.models import Asset, AssetCategory
from users.models import User

from .serializers import (
    TicketSerializer, TicketCommentSerializer, CategorySerializer,
    IncidentSerializer, IncidentUpdateSerializer,
    ChangeRequestSerializer, ChangeApprovalSerializer,
    AssetSerializer, AssetCategorySerializer,
    UserBriefSerializer,
)
from itsm.notifications import (
    notify_ticket_created, notify_ticket_assigned, notify_ticket_resolved,
    notify_incident_created, notify_change_submitted, notify_ticket_comment,
    notify_change_approved, notify_change_rejected, notify_incident_resolved,
)
from tickets.sla_service import attach_sla, record_first_response


# ── Permission helpers ───────────────────────────────────────────────────────

class IsAgentOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and request.user.is_agent

class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin_role


# ── Tickets ──────────────────────────────────────────────────────────────────

class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'category', 'assigned_to']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Ticket.objects.none()
        qs = Ticket.objects.select_related('created_by', 'assigned_to', 'category')
        if not self.request.user.is_agent:
            qs = qs.filter(created_by=self.request.user)
        return qs

    def get_permissions(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsAgentOrReadOnly()]
        return super().get_permissions()

    def perform_create(self, serializer):
        ticket = serializer.save(created_by=self.request.user)
        attach_sla(ticket)
        notify_ticket_created(ticket)

    def perform_update(self, serializer):
        old = self.get_object()
        old_assigned = old.assigned_to
        ticket = serializer.save()
        if ticket.assigned_to and ticket.assigned_to != old_assigned:
            notify_ticket_assigned(ticket, self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAgentOrReadOnly])
    def resolve(self, request, pk=None):
        ticket = self.get_object()
        if ticket.status in ['resolved', 'closed']:
            return Response({'detail': 'Already resolved.'}, status=status.HTTP_400_BAD_REQUEST)
        ticket.resolve()
        notify_ticket_resolved(ticket)
        return Response(TicketSerializer(ticket).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAgentOrReadOnly])
    def close(self, request, pk=None):
        ticket = self.get_object()
        ticket.status = Ticket.Status.CLOSED
        ticket.save()
        return Response(TicketSerializer(ticket).data)

    @action(detail=True, methods=['get', 'post'])
    def comments(self, request, pk=None):
        ticket = self.get_object()
        if request.method == 'GET':
            qs = ticket.comments.select_related('author')
            if not request.user.is_agent:
                qs = qs.filter(is_internal=False)
            return Response(TicketCommentSerializer(qs, many=True).data)
        serializer = TicketCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(ticket=ticket, author=request.user)
        if not request.user.is_agent:
            comment.is_internal = False
            comment.save()
        record_first_response(ticket, request.user)
        notify_ticket_comment(ticket, comment)
        return Response(TicketCommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAgentOrReadOnly]


# ── Incidents ────────────────────────────────────────────────────────────────

class IncidentViewSet(viewsets.ModelViewSet):
    serializer_class = IncidentSerializer
    permission_classes = [IsAgentOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'severity', 'assigned_to']
    search_fields = ['title', 'description']
    ordering = ['-created_at']

    def get_queryset(self):
        return Incident.objects.select_related('reported_by', 'assigned_to')

    def perform_create(self, serializer):
        incident = serializer.save(reported_by=self.request.user)
        notify_incident_created(incident)

    @action(detail=True, methods=['post'], permission_classes=[IsAgentOrReadOnly])
    def add_update(self, request, pk=None):
        incident = self.get_object()
        message = request.data.get('message', '')
        new_status = request.data.get('status')
        if not message:
            return Response({'detail': 'Message required.'}, status=status.HTTP_400_BAD_REQUEST)
        if new_status and new_status in dict(Incident.Status.choices):
            if new_status == Incident.Status.RESOLVED and incident.status != new_status:
                incident.resolve()
                notify_incident_resolved(incident)
            else:
                incident.status = new_status
                incident.save()
        update = IncidentUpdate.objects.create(
            incident=incident, author=request.user,
            message=message, status_at_time=incident.status
        )
        return Response(IncidentUpdateSerializer(update).data, status=status.HTTP_201_CREATED)


# ── Changes ──────────────────────────────────────────────────────────────────

class ChangeRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ChangeRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'change_type', 'risk_level']
    search_fields = ['title', 'description']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ChangeRequest.objects.none()
        qs = ChangeRequest.objects.select_related('requested_by', 'assigned_to', 'approved_by')
        if not self.request.user.is_agent:
            qs = qs.filter(requested_by=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    def _check_editable(self, change):
        user = self.request.user
        if user.is_admin_role:
            return
        if change.requested_by != user or change.status != ChangeRequest.Status.DRAFT:
            raise PermissionDenied('Only your own draft changes can be modified.')

    def perform_update(self, serializer):
        self._check_editable(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_editable(instance)
        instance.delete()

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        change = self.get_object()
        if change.status != ChangeRequest.Status.DRAFT:
            return Response({'detail': 'Only draft changes can be submitted.'}, status=400)
        if change.requested_by != request.user and not request.user.is_admin_role:
            return Response({'detail': 'Forbidden.'}, status=403)
        change.status = ChangeRequest.Status.SUBMITTED
        change.save()
        notify_change_submitted(change)
        return Response(ChangeRequestSerializer(change).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminRole])
    def approve(self, request, pk=None):
        change = self.get_object()
        decision = request.data.get('decision', 'approved')
        comments = request.data.get('comments', '')
        if decision not in dict(ChangeApproval.Decision.choices):
            return Response({'detail': 'Invalid decision.'}, status=400)
        if change.status not in (ChangeRequest.Status.SUBMITTED, ChangeRequest.Status.UNDER_REVIEW):
            return Response({'detail': 'Change is not awaiting a decision.'}, status=400)
        approval, created = ChangeApproval.objects.get_or_create(
            change=change, approver=request.user,
            defaults={'decision': decision, 'comments': comments}
        )
        if not created:
            return Response({'detail': 'You have already recorded a decision.'}, status=409)
        if decision == ChangeApproval.Decision.APPROVED:
            change.status = ChangeRequest.Status.APPROVED
            change.approved_by = request.user
            change.approved_at = timezone.now()
            change.save()
            notify_change_approved(change)
        elif decision == ChangeApproval.Decision.REJECTED:
            change.status = ChangeRequest.Status.REJECTED
            change.save()
            notify_change_rejected(change)
        return Response(ChangeRequestSerializer(change).data)


# ── Assets ───────────────────────────────────────────────────────────────────

class AssetViewSet(viewsets.ModelViewSet):
    serializer_class = AssetSerializer
    permission_classes = [IsAgentOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'asset_type', 'category', 'assigned_to', 'department']
    search_fields = ['name', 'asset_tag', 'serial_number', 'manufacturer']
    ordering = ['asset_tag']

    def get_queryset(self):
        return Asset.objects.select_related('category', 'assigned_to')

    @action(detail=True, methods=['post'])
    def retire(self, request, pk=None):
        asset = self.get_object()
        asset.status = Asset.Status.RETIRED
        asset.assigned_to = None
        asset.save()
        return Response(AssetSerializer(asset).data)


class AssetCategoryViewSet(viewsets.ModelViewSet):
    queryset = AssetCategory.objects.all()
    serializer_class = AssetCategorySerializer
    permission_classes = [IsAgentOrReadOnly]


# ── Users (read-only for agents) ─────────────────────────────────────────────

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(is_active=True).order_by('username')
    serializer_class = UserBriefSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'first_name', 'last_name', 'email']
