from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'tel', 'role',
            'is_active', 'setup_required', 'setup_completed_at',
            'date_joined', 'last_login', 'has_keys'
        ]
        read_only_fields = [
            'id', 'date_joined', 'last_login', 'setup_completed_at', 'has_keys'
        ]


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            # Try to authenticate the user
            user = authenticate(
                request=self.context.get('request'),
                username=email,
                password=password
            )
            
            if not user:
                raise serializers.ValidationError(
                    'Unable to log in with provided credentials.'
                )
            
            if not user.is_active:
                raise serializers.ValidationError(
                    'User account is disabled.'
                )
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError(
                'Must include email and password.'
            )


class SetupSerializer(serializers.Serializer):
    """Serializer for user setup (password setting and key generation)."""
    
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    
    def validate_password(self, value):
        """Validate password using Django's password validators."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, attrs):
        """Validate that passwords match and user exists."""
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')
        email = attrs.get('email')
        
        # Check if passwords match
        if password != password_confirm:
            raise serializers.ValidationError(
                {'password_confirm': 'Passwords do not match.'}
            )
        
        # Check if user exists and requires setup
        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {'email': 'User does not exist or is not active.'}
            )
        
        if not user.setup_required:
            raise serializers.ValidationError(
                {'email': 'User setup has already been completed.'}
            )
        
        attrs['user'] = user
        return attrs
    
    def save(self):
        """Complete user setup."""
        user = self.validated_data['user']
        password = self.validated_data['password']
        
        # Complete the setup
        user.complete_setup(password)
        
        return user


class UserKeysSerializer(serializers.ModelSerializer):
    """Serializer for user keys (public key only for security)."""
    
    class Meta:
        model = User
        fields = ['id', 'email', 'public_key', 'has_keys']
        read_only_fields = ['id', 'email', 'public_key', 'has_keys']