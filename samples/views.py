# samples/views.py
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from django.utils import timezone
import logging

from .models import Client, Project
from .serializers import (
    ClientSerializer,
    ClientListSerializer, 
    ClientCreateUpdateSerializer,
    ClientDetailSerializer
)

logger = logging.getLogger(__name__)


class ClientPagination(PageNumberPagination):
    """Custom pagination for client list."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def client_list_create(request):
    """
    GET: List all clients with optional filtering and search
    POST: Create a new client
    """
    
    if request.method == 'GET':
        # Get all clients
        queryset = Client.objects.select_related('created_by').annotate(
            projects_count=Count('projects')
        )
        
        # Apply filters
        client_type = request.query_params.get('client_type')
        if client_type:
            queryset = queryset.filter(client_type=client_type)
        
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_active=is_active_bool)
        
        # Search functionality
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(contact_person__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )
        
        # Ordering
        ordering = request.query_params.get('ordering', 'name')
        valid_orderings = ['name', '-name', 'created_at', '-created_at', 'client_type', '-client_type']
        if ordering in valid_orderings:
            queryset = queryset.order_by(ordering)
        
        # Pagination
        paginator = ClientPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = ClientListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        # If no pagination
        serializer = ClientListSerializer(queryset, many=True)
        return Response({
            'success': True,
            'count': queryset.count(),
            'results': serializer.data
        })
    
    elif request.method == 'POST':
        # Create new client
        serializer = ClientCreateUpdateSerializer(
            data=request.data, 
            context={'request': request}
        )
        
        if serializer.is_valid():
            # Set the created_by field
            client = serializer.save(created_by=request.user)
            
            # Return the created client with full details
            response_serializer = ClientSerializer(client)
            
            logger.info(f"Client '{client.name}' created by user {request.user.email}")
            
            return Response({
                'success': True,
                'message': 'Client created successfully',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'message': 'Failed to create client',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def client_detail(request, client_id):
    """
    GET: Retrieve a specific client with full details
    PUT/PATCH: Update a specific client
    DELETE: Delete a specific client
    """
    
    try:
        client = get_object_or_404(
            Client.objects.select_related('created_by').prefetch_related('projects'),
            id=client_id
        )
    except Client.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Client not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        # Retrieve client details
        serializer = ClientDetailSerializer(client)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method in ['PUT', 'PATCH']:
        # Update client
        partial = request.method == 'PATCH'
        serializer = ClientCreateUpdateSerializer(
            client, 
            data=request.data, 
            partial=partial,
            context={'request': request}
        )
        
        if serializer.is_valid():
            updated_client = serializer.save()
            
            # Return updated client
            response_serializer = ClientSerializer(updated_client)
            
            logger.info(f"Client '{updated_client.name}' updated by user {request.user.email}")
            
            return Response({
                'success': True,
                'message': 'Client updated successfully',
                'data': response_serializer.data
            })
        
        return Response({
            'success': False,
            'message': 'Failed to update client',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Delete client
        client_name = client.name
        
        # Check if client has associated projects or samples
        projects_count = client.projects.count()
        samples_count = client.samples.count() if hasattr(client, 'samples') else 0
        
        if projects_count > 0 or samples_count > 0:
            return Response({
                'success': False,
                'message': f'Cannot delete client. Client has {projects_count} associated projects and {samples_count} samples. Please remove these first or deactivate the client instead.',
                'has_dependencies': True,
                'dependencies': {
                    'projects': projects_count,
                    'samples': samples_count
                }
            }, status=status.HTTP_409_CONFLICT)
        
        client.delete()
        
        logger.info(f"Client '{client_name}' deleted by user {request.user.email}")
        
        return Response({
            'success': True,
            'message': f'Client "{client_name}" deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def client_toggle_status(request, client_id):
    """
    Toggle client active/inactive status.
    Safer alternative to deletion for clients with dependencies.
    """
    
    try:
        client = get_object_or_404(Client, id=client_id)
    except Client.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Client not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Toggle the status
    client.is_active = not client.is_active
    client.save(update_fields=['is_active', 'updated_at'])
    
    status_text = 'activated' if client.is_active else 'deactivated'
    
    logger.info(f"Client '{client.name}' {status_text} by user {request.user.email}")
    
    return Response({
        'success': True,
        'message': f'Client "{client.name}" {status_text} successfully',
        'data': {
            'id': client.id,
            'name': client.name,
            'is_active': client.is_active
        }
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def client_stats(request):
    """
    Get client statistics and summary information.
    """
    
    total_clients = Client.objects.count()
    active_clients = Client.objects.filter(is_active=True).count()
    inactive_clients = total_clients - active_clients
    
    # Clients by type
    client_types = Client.objects.values('client_type').annotate(
        count=Count('id')
    ).order_by('client_type')
    
    # Recent clients (last 30 days)
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    recent_clients = Client.objects.filter(
        created_at__gte=thirty_days_ago
    ).count()
    
    stats = {
        'total_clients': total_clients,
        'active_clients': active_clients,
        'inactive_clients': inactive_clients,
        'recent_clients': recent_clients,
        'client_types': list(client_types)
    }
    
    return Response({
        'success': True,
        'data': stats
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def client_search(request):
    """
    Advanced search endpoint for clients.
    Supports multiple search parameters and filters.
    """
    
    query = request.query_params.get('q', '').strip()
    
    if not query:
        return Response({
            'success': False,
            'message': 'Search query is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Search in multiple fields
    clients = Client.objects.filter(
        Q(name__icontains=query) |
        Q(contact_person__icontains=query) |
        Q(email__icontains=query) |
        Q(phone__icontains=query) |
        Q(address__icontains=query)
    ).select_related('created_by')[:20]  # Limit to 20 results
    
    serializer = ClientListSerializer(clients, many=True)
    
    return Response({
        'success': True,
        'query': query,
        'count': len(serializer.data),
        'results': serializer.data
    })