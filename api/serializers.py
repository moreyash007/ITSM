from rest_framework import serializers
from tickets.models import Ticket, TicketComment, Category, TicketSLA
from incidents.models import Incident, IncidentUpdate
from changes.models import ChangeRequest, ChangeApproval
from assets.models import Asset, AssetCategory
from users.models import User


# ── Users ───────────────────────────────────────────────────────────────────

class UserBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'email', 'role', 'department']

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.username


# ── Tickets ─────────────────────────────────────────────────────────────────

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


class TicketSLASerializer(serializers.ModelSerializer):
    time_remaining = serializers.CharField(read_only=True)
    resolution_percent = serializers.IntegerField(read_only=True)
    is_breached = serializers.BooleanField(read_only=True)

    class Meta:
        model = TicketSLA
        fields = [
            'response_due', 'resolution_due', 'first_response_at',
            'response_breached', 'resolution_breached',
            'time_remaining', 'resolution_percent', 'is_breached',
        ]


class TicketCommentSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)

    class Meta:
        model = TicketComment
        fields = ['id', 'author', 'body', 'is_internal', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']


class TicketSerializer(serializers.ModelSerializer):
    created_by = UserBriefSerializer(read_only=True)
    assigned_to = UserBriefSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role__in=['admin', 'agent']),
        source='assigned_to', write_only=True, required=False, allow_null=True
    )
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category',
        write_only=True, required=False, allow_null=True
    )
    ticket_id = serializers.CharField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    sla = TicketSLASerializer(read_only=True)
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_id', 'title', 'description', 'priority', 'status',
            'category', 'category_id', 'created_by', 'assigned_to', 'assigned_to_id',
            'created_at', 'updated_at', 'resolved_at', 'due_date',
            'is_overdue', 'sla', 'comment_count',
        ]
        read_only_fields = ['id', 'ticket_id', 'created_by', 'created_at', 'updated_at', 'resolved_at']

    def get_comment_count(self, obj) -> int:
        return obj.comments.count()


# ── Incidents ────────────────────────────────────────────────────────────────

class IncidentUpdateSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)

    class Meta:
        model = IncidentUpdate
        fields = ['id', 'author', 'message', 'status_at_time', 'created_at']
        read_only_fields = ['id', 'author', 'status_at_time', 'created_at']


class IncidentSerializer(serializers.ModelSerializer):
    reported_by = UserBriefSerializer(read_only=True)
    assigned_to = UserBriefSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role__in=['admin', 'agent']),
        source='assigned_to', write_only=True, required=False, allow_null=True
    )
    incident_id = serializers.CharField(read_only=True)
    duration = serializers.CharField(read_only=True)

    class Meta:
        model = Incident
        fields = [
            'id', 'incident_id', 'title', 'description', 'severity', 'status',
            'reported_by', 'assigned_to', 'assigned_to_id',
            'affected_services', 'root_cause', 'resolution',
            'created_at', 'updated_at', 'resolved_at', 'duration',
        ]
        read_only_fields = ['id', 'incident_id', 'reported_by', 'created_at', 'updated_at']


# ── Changes ──────────────────────────────────────────────────────────────────

class ChangeApprovalSerializer(serializers.ModelSerializer):
    approver = UserBriefSerializer(read_only=True)

    class Meta:
        model = ChangeApproval
        fields = ['id', 'approver', 'decision', 'comments', 'decided_at']
        read_only_fields = ['id', 'approver', 'decided_at']


class ChangeRequestSerializer(serializers.ModelSerializer):
    requested_by = UserBriefSerializer(read_only=True)
    assigned_to = UserBriefSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role__in=['admin', 'agent']),
        source='assigned_to', write_only=True, required=False, allow_null=True
    )
    change_id = serializers.CharField(read_only=True)
    approvals = ChangeApprovalSerializer(many=True, read_only=True)

    class Meta:
        model = ChangeRequest
        fields = [
            'id', 'change_id', 'title', 'description', 'change_type', 'status',
            'risk_level', 'justification', 'implementation_plan', 'rollback_plan', 'test_plan',
            'scheduled_start', 'scheduled_end', 'requested_by', 'assigned_to', 'assigned_to_id',
            'created_at', 'updated_at', 'approved_at', 'approvals',
        ]
        read_only_fields = ['id', 'change_id', 'requested_by', 'created_at', 'updated_at', 'approved_at']


# ── Assets ───────────────────────────────────────────────────────────────────

class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = ['id', 'name', 'description']


class AssetSerializer(serializers.ModelSerializer):
    assigned_to = UserBriefSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        source='assigned_to', write_only=True, required=False, allow_null=True
    )
    category = AssetCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=AssetCategory.objects.all(), source='category',
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'asset_tag', 'asset_type', 'category', 'category_id', 'status',
            'manufacturer', 'model_number', 'serial_number', 'location', 'department',
            'assigned_to', 'assigned_to_id',
            'purchase_date', 'warranty_expiry', 'purchase_cost',
            'ip_address', 'mac_address', 'os_version', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
