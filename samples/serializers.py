# samples/serializers.py
from rest_framework import serializers
from .models import Client, Project
from django.utils import timezone


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for Client model."""
    
    # Read-only fields to include in the response
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    projects_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Client
        fields = [
            'id', 'name', 'contact_person', 'email', 'phone', 'address',
            'client_type', 'is_active', 'default_sla_hours', 
            'billing_contact', 'billing_email',
            'created_at', 'updated_at', 'created_by',
            'created_by_name', 'created_by_email', 'projects_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def get_projects_count(self, obj):
        """Get the number of projects for this client."""
        return obj.projects.count()
    
    def create(self, validated_data):
        """Create a new client and set the created_by field."""
        # Get the user from the request context
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)


class ClientListSerializer(serializers.ModelSerializer):
    """Simplified serializer for client list views."""
    
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    projects_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Client
        fields = [
            'id', 'name', 'contact_person', 'email', 'phone', 'address',
            'client_type', 'is_active', 'default_sla_hours',
            'billing_contact', 'billing_email',
            'created_at', 'updated_at', 'created_by', 'created_by_name', 'projects_count'
        ]
    
    def get_projects_count(self, obj):
        return obj.projects.count()


class ClientCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating clients."""
    
    class Meta:
        model = Client
        fields = [
            'name', 'contact_person', 'email', 'phone', 'address',
            'client_type', 'is_active', 'default_sla_hours',
            'billing_contact', 'billing_email'
        ]
    
    def validate_email(self, value):
        """Validate that email is unique (case-insensitive)."""
        # For updates, exclude the current instance
        queryset = Client.objects.filter(email__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError("A client with this email already exists.")
        return value
    
    def validate_name(self, value):
        """Validate that client name is not empty after stripping whitespace."""
        if not value.strip():
            raise serializers.ValidationError("Client name cannot be empty.")
        return value.strip()


class ProjectSerializer(serializers.ModelSerializer):
    """Basic serializer for Project model (for client details)."""
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'status', 
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClientDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for client detail view with related projects."""
    
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    projects = ProjectSerializer(many=True, read_only=True)
    projects_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Client
        fields = [
            'id', 'name', 'contact_person', 'email', 'phone', 'address',
            'client_type', 'is_active', 'default_sla_hours',
            'billing_contact', 'billing_email',
            'created_at', 'updated_at', 'created_by',
            'created_by_name', 'created_by_email', 
            'projects', 'projects_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def get_projects_count(self, obj):
        return obj.projects.count()

class ProjectListSerializer(serializers.ModelSerializer):
    """Simplified serializer for project list views."""
    
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_id = serializers.UUIDField(source='client.id', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    samples_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'status',
            'client_id', 'client_name', 
            'created_at', 'updated_at', 'completed_at',
            'created_by', 'created_by_name', 'samples_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_samples_count(self, obj):
        """Get the number of samples for this project."""
        return obj.samples.count() if hasattr(obj, 'samples') else 0


class ProjectCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating projects."""
    
    class Meta:
        model = Project
        fields = [
            'name', 'description', 'client', 'status', 'completed_at'
        ]
    
    def validate_name(self, value):
        """Validate that project name is not empty after stripping whitespace."""
        if not value.strip():
            raise serializers.ValidationError("Project name cannot be empty.")
        return value.strip()
    
    def validate_client(self, value):
        """Validate that the client is active."""
        if not value.is_active:
            raise serializers.ValidationError("Cannot create project for inactive client.")
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        # If status is COMPLETED, completed_at should be set
        if data.get('status') == 'COMPLETED' and not data.get('completed_at'):
            data['completed_at'] = timezone.now()
        
        # If status is not COMPLETED, completed_at should be None
        if data.get('status') != 'COMPLETED':
            data['completed_at'] = None
        
        return data


class ProjectDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for project detail view with related data."""
    
    client = ClientListSerializer(read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    samples_count = serializers.SerializerMethodField()
    recent_samples = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'status',
            'client', 'created_at', 'updated_at', 'completed_at',
            'created_by', 'created_by_name', 'created_by_email',
            'samples_count', 'recent_samples'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def get_samples_count(self, obj):
        """Get the number of samples for this project."""
        return obj.samples.count() if hasattr(obj, 'samples') else 0
    
    def get_recent_samples(self, obj):
        """Get the 5 most recent samples for this project."""
        if hasattr(obj, 'samples'):
            recent_samples = obj.samples.select_related('batch').order_by('-received_at')[:5]
            return [{
                'id': sample.id,
                'sample_number': sample.sample_number,
                'batch_number': sample.batch.batch_number,
                'received_at': sample.received_at,
                'status': sample.status
            } for sample in recent_samples]
        return []


# Update the existing ProjectSerializer to be more comprehensive
class ProjectSerializer(serializers.ModelSerializer):
    """Enhanced basic serializer for Project model."""
    
    client_name = serializers.CharField(source='client.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    samples_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'status', 
            'client', 'client_name',
            'created_at', 'updated_at', 'completed_at',
            'created_by', 'created_by_name', 'samples_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def get_samples_count(self, obj):
        """Get the number of samples for this project."""
        return obj.samples.count() if hasattr(obj, 'samples') else 0