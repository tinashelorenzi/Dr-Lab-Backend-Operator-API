# samples/serializers.py
from rest_framework import serializers
from .models import Client, Project


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