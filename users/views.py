from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import login
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging

from .models import User, UserSession
from .serializers import (
    LoginSerializer, 
    SetupSerializer, 
    UserSerializer,
    UserKeysSerializer
)

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Get the client IP address from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    """
    API endpoint for user login.
    
    Returns user data and authentication token upon successful login.
    Also indicates whether user needs to complete setup.
    """
    serializer = LoginSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Update last login time
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        # Create or get authentication token
        token, created = Token.objects.get_or_create(user=user)
        
        # Create user session record
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        
        # Create or update session record
        user_session, created = UserSession.objects.get_or_create(
            user=user,
            session_key=session_key,
            defaults={
                'ip_address': get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'is_active': True
            }
        )
        
        if not created:
            user_session.ip_address = get_client_ip(request)
            user_session.user_agent = request.META.get('HTTP_USER_AGENT', '')
            user_session.is_active = True
            user_session.save()
        
        # Serialize user data
        user_data = UserSerializer(user).data
        
        logger.info(f"User {user.email} logged in successfully")
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'token': token.key,
            'user': user_data,
            'requires_setup': user.setup_required
        }, status=status.HTTP_200_OK)
    
    return Response({
        'success': False,
        'message': 'Invalid credentials',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def setup_view(request):
    """
    API endpoint for user setup (password setting and key generation).
    
    This endpoint allows users to set their password and generates their cryptographic keys.
    """
    serializer = SetupSerializer(data=request.data)
    
    if serializer.is_valid():
        try:
            user = serializer.save()
            
            # Create authentication token
            token, created = Token.objects.get_or_create(user=user)
            
            # Create user session record
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key
            
            UserSession.objects.create(
                user=user,
                session_key=session_key,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                is_active=True
            )
            
            # Serialize user data
            user_data = UserSerializer(user).data
            
            logger.info(f"User {user.email} completed setup successfully")
            
            return Response({
                'success': True,
                'message': 'Setup completed successfully',
                'token': token.key,
                'user': user_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Setup failed for user: {str(e)}")
            return Response({
                'success': False,
                'message': 'Setup failed due to server error',
                'errors': {'non_field_errors': [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'success': False,
        'message': 'Invalid setup data',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """
    API endpoint for user logout.
    
    Deactivates the user session and deletes the authentication token.
    """
    try:
        # Deactivate user sessions
        UserSession.objects.filter(
            user=request.user,
            session_key=request.session.session_key
        ).update(is_active=False)
        
        # Delete the token
        try:
            token = Token.objects.get(user=request.user)
            token.delete()
        except Token.DoesNotExist:
            pass
        
        logger.info(f"User {request.user.email} logged out successfully")
        
        return Response({
            'success': True,
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Logout failed for user {request.user.email}: {str(e)}")
        return Response({
            'success': False,
            'message': 'Logout failed',
            'errors': {'non_field_errors': [str(e)]}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def profile_view(request):
    """
    API endpoint to get current user profile.
    """
    # Update last ping
    request.user.update_last_ping()
    
    user_data = UserSerializer(request.user).data
    
    return Response({
        'success': True,
        'user': user_data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_keys_view(request):
    """
    API endpoint to get user's public key.
    
    Note: Private key is never returned for security reasons.
    """
    if not request.user.has_keys:
        return Response({
            'success': False,
            'message': 'User has not generated keys yet'
        }, status=status.HTTP_404_NOT_FOUND)
    
    keys_data = UserKeysSerializer(request.user).data
    
    return Response({
        'success': True,
        'keys': keys_data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def ping_view(request):
    """
    API endpoint for heartbeat/ping to update user's last activity.
    """
    request.user.update_last_ping()
    
    return Response({
        'success': True,
        'message': 'Ping updated',
        'timestamp': request.user.last_ping
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_setup_status(request):
    """
    API endpoint to check if user needs to complete setup.
    """
    return Response({
        'success': True,
        'requires_setup': request.user.setup_required,
        'has_keys': request.user.has_keys,
        'setup_completed_at': request.user.setup_completed_at
    }, status=status.HTTP_200_OK)