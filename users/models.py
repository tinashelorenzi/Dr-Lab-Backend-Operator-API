from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
import base64
import os
import uuid


class UserManager(BaseUserManager):
    """Custom user manager for the User model."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user with an email and password."""
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        # If password is provided, set it. Otherwise, mark setup as required
        if password:
            user.set_password(password)
            user.setup_required = False
        else:
            user.setup_required = True
            
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser with an email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'ADMIN')
        extra_fields.setdefault('setup_required', False)
        
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
    
    # Setup and security
    setup_required = models.BooleanField(
        default=True, 
        help_text="If True, user needs to complete initial setup (password and keys)"
    )
    setup_completed_at = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Timestamp when user completed initial setup"
    )
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    last_ping = models.DateTimeField(null=True, blank=True, help_text="Last heartbeat timestamp")
    
    # Cryptographic keys for secure operations
    private_key_encrypted = models.TextField(
        blank=True, 
        null=True, 
        help_text="Encrypted RSA Private Key"
    )
    public_key = models.TextField(
        blank=True, 
        null=True, 
        help_text="RSA Public Key (PEM format)"
    )
    key_salt = models.CharField(
        max_length=64, 
        blank=True, 
        null=True, 
        help_text="Salt used for private key encryption"
    )
    
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
    
    def _derive_key_from_password(self, password: str, salt: bytes = None) -> tuple:
        """Derive encryption key from password using PBKDF2."""
        if salt is None:
            salt = os.urandom(32)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    def generate_key_pair(self, password: str):
        """Generate RSA key pair for the user and encrypt private key with password."""
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
        )
        
        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Encrypt private key with user's password
        encryption_key, salt = self._derive_key_from_password(password)
        fernet = Fernet(encryption_key)
        encrypted_private_key = fernet.encrypt(private_pem)
        
        # Store encrypted private key and public key
        self.private_key_encrypted = base64.b64encode(encrypted_private_key).decode('utf-8')
        self.public_key = public_pem
        self.key_salt = base64.b64encode(salt).decode('utf-8')
        self.save(update_fields=['private_key_encrypted', 'public_key', 'key_salt'])
        
        return public_pem
    
    def get_private_key(self, password: str) -> str:
        """Decrypt and return the private key using the user's password."""
        if not self.private_key_encrypted or not self.key_salt:
            raise ValueError("No encrypted private key found for user")
        
        try:
            # Derive the decryption key
            salt = base64.b64decode(self.key_salt.encode())
            encryption_key, _ = self._derive_key_from_password(password, salt)
            
            # Decrypt the private key
            fernet = Fernet(encryption_key)
            encrypted_data = base64.b64decode(self.private_key_encrypted.encode())
            decrypted_private_key = fernet.decrypt(encrypted_data)
            
            return decrypted_private_key.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decrypt private key: {str(e)}")
    
    def complete_setup(self, password: str):
        """Complete user setup with password and generate keys."""
        # Set the password
        self.set_password(password)
        
        # Generate key pair
        self.generate_key_pair(password)
        
        # Mark setup as completed
        self.setup_required = False
        self.setup_completed_at = timezone.now()
        
        self.save(update_fields=['password', 'setup_required', 'setup_completed_at'])
        
        return True
    
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
    
    @property
    def has_keys(self):
        """Check if user has generated keys."""
        return bool(self.private_key_encrypted and self.public_key)


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