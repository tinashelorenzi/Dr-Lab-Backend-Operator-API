from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import uuid


class UserManager(BaseUserManager):
    """Custom user manager for the User model."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user with an email and password."""
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser with an email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'ADMIN')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model for the LIMS system."""
    
    # Role choices for User Access Control
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('MANAGER', 'Lab Manager'),
        ('TECHNICIAN', 'Lab Technician'),
        ('OPERATOR', 'Lab Operator'),
        ('VIEWER', 'Viewer'),
    ]
    
    # Primary user information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, max_length=255)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    # Contact information
    tel = models.CharField(max_length=20, blank=True, null=True, help_text="Phone number")
    
    # User status and permissions
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='VIEWER')
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    last_ping = models.DateTimeField(null=True, blank=True, help_text="Last heartbeat timestamp")
    
    # Cryptographic keys for secure operations
    private_key = models.TextField(blank=True, null=True, help_text="RSA Private Key (PEM format)")
    public_key = models.TextField(blank=True, null=True, help_text="RSA Public Key (PEM format)")
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.email
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name if self.first_name else self.email
    
    def update_last_ping(self):
        """Update the last_ping timestamp to now."""
        self.last_ping = timezone.now()
        self.save(update_fields=['last_ping'])
    
    def generate_key_pair(self):
        """Generate RSA key pair for the user."""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Get public key
        public_key = private_key.public_key()
        
        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        self.private_key = private_pem
        self.public_key = public_pem
        self.save(update_fields=['private_key', 'public_key'])
        
        return private_pem, public_pem
    
    def is_online(self, threshold_minutes=5):
        """Check if user is considered online based on last_ping."""
        if not self.last_ping:
            return False
        
        threshold = timezone.now() - timezone.timedelta(minutes=threshold_minutes)
        return self.last_ping > threshold
    
    def has_role(self, role):
        """Check if user has a specific role."""
        return self.role == role
    
    def can_manage_users(self):
        """Check if user can manage other users."""
        return self.role in ['ADMIN', 'MANAGER']
    
    def can_modify_samples(self):
        """Check if user can modify samples."""
        return self.role in ['ADMIN', 'MANAGER', 'TECHNICIAN', 'OPERATOR']
    
    def can_view_reports(self):
        """Check if user can view reports."""
        return True  # All users can view reports
    
    @property
    def is_admin(self):
        """Check if user is an admin."""
        return self.role == 'ADMIN'
    
    @property
    def is_manager(self):
        """Check if user is a manager."""
        return self.role == 'MANAGER'


class UserSession(models.Model):
    """Track user sessions for security and monitoring purposes."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_sessions'
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.user.email} - {self.session_key[:10]}..."
    
    def deactivate(self):
        """Deactivate the session."""
        self.is_active = False
        self.save(update_fields=['is_active'])