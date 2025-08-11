from django.db import models
from django.utils import timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import uuid
from users.models import User


class Group(models.Model):
    """
    Model for messaging groups with cryptographic capabilities.
    Each group has its own key pair for secure messaging.
    """
    
    GROUP_TYPES = [
        ('PUBLIC', 'Public Group'),
        ('PRIVATE', 'Private Group'),
        ('SYSTEM', 'System Group'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Group name")
    description = models.TextField(blank=True, help_text="Group description")
    group_type = models.CharField(max_length=20, choices=GROUP_TYPES, default='PRIVATE')
    
    # Group management
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_groups',
        help_text="User who created this group"
    )
    admins = models.ManyToManyField(
        User, 
        related_name='admin_groups',
        help_text="Users who can manage this group"
    )
    members = models.ManyToManyField(
        User, 
        through='GroupMembership',
        through_fields=('group', 'user'),
        related_name='user_groups',
        help_text="Users who are members of this group"
    )
    
    # Group settings
    is_active = models.BooleanField(default=True)
    max_members = models.PositiveIntegerField(
        default=50,
        help_text="Maximum number of members allowed"
    )
    allow_member_invite = models.BooleanField(
        default=False,
        help_text="Allow members to invite others"
    )
    
    # Cryptographic keys for secure messaging
    private_key = models.TextField(
        blank=True, 
        null=True, 
        help_text="RSA Private Key (PEM format) for group encryption"
    )
    public_key = models.TextField(
        blank=True, 
        null=True, 
        help_text="RSA Public Key (PEM format) for group encryption"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'groups'
        verbose_name = 'Group'
        verbose_name_plural = 'Groups'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.group_type})"
    
    def save(self, *args, **kwargs):
        """Override save to generate keys if they don't exist."""
        if not self.private_key or not self.public_key:
            self.generate_key_pair()
        super().save(*args, **kwargs)
    
    def generate_key_pair(self):
        """Generate RSA key pair for the group."""
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
        
        return private_pem, public_pem
    
    def add_member(self, user, added_by=None, role='MEMBER'):
        """Add a user to the group."""
        if self.members.filter(id=user.id).exists():
            return False, "User is already a member"
        
        if self.members.count() >= self.max_members:
            return False, "Group has reached maximum members"
        
        membership, created = GroupMembership.objects.get_or_create(
            group=self,
            user=user,
            defaults={
                'role': role,
                'added_by': added_by,
                'joined_at': timezone.now()
            }
        )
        
        # Update last activity
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
        
        return created, "User added successfully" if created else "User was already a member"
    
    def remove_member(self, user):
        """Remove a user from the group."""
        try:
            membership = GroupMembership.objects.get(group=self, user=user)
            membership.delete()
            
            # Update last activity
            self.last_activity = timezone.now()
            self.save(update_fields=['last_activity'])
            
            return True, "User removed successfully"
        except GroupMembership.DoesNotExist:
            return False, "User is not a member of this group"
    
    def is_admin(self, user):
        """Check if user is an admin of this group."""
        return self.admins.filter(id=user.id).exists()
    
    def is_member(self, user):
        """Check if user is a member of this group."""
        return self.members.filter(id=user.id).exists()
    
    def can_user_invite(self, user):
        """Check if user can invite others to this group."""
        if self.is_admin(user):
            return True
        return self.allow_member_invite and self.is_member(user)
    
    @property
    def member_count(self):
        """Get the number of members in the group."""
        return self.members.count()
    
    @property
    def has_keys(self):
        """Check if group has generated keys."""
        return bool(self.private_key and self.public_key)


class GroupMembership(models.Model):
    """
    Through model for Group-User relationship with additional metadata.
    """
    
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('MODERATOR', 'Moderator'),
        ('MEMBER', 'Member'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER')
    
    # Membership metadata
    added_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='invited_memberships',
        help_text="User who added this member"
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'group_memberships'
        verbose_name = 'Group Membership'
        verbose_name_plural = 'Group Memberships'
        unique_together = ['group', 'user']
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.user.get_full_name()} in {self.group.name} ({self.role})"
    
    def update_last_seen(self):
        """Update the last seen timestamp."""
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])


class GroupInvitation(models.Model):
    """
    Model for group invitations.
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('DECLINED', 'Declined'),
        ('EXPIRED', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='invitations')
    invited_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='group_invitations'
    )
    invited_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_group_invitations'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    message = models.TextField(blank=True, help_text="Optional invitation message")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        help_text="Invitation expiry date"
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'group_invitations'
        verbose_name = 'Group Invitation'
        verbose_name_plural = 'Group Invitations'
        unique_together = ['group', 'invited_user']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invitation for {self.invited_user.get_full_name()} to {self.group.name}"
    
    def save(self, *args, **kwargs):
        """Set expiry date if not provided."""
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)
    
    def accept(self):
        """Accept the invitation."""
        if self.status != 'PENDING':
            return False, "Invitation is not pending"
        
        if timezone.now() > self.expires_at:
            self.status = 'EXPIRED'
            self.save()
            return False, "Invitation has expired"
        
        # Add user to group
        success, message = self.group.add_member(
            user=self.invited_user,
            added_by=self.invited_by,
            role='MEMBER'
        )
        
        if success:
            self.status = 'ACCEPTED'
            self.responded_at = timezone.now()
            self.save()
            return True, "Invitation accepted successfully"
        
        return False, message
    
    def decline(self):
        """Decline the invitation."""
        if self.status != 'PENDING':
            return False, "Invitation is not pending"
        
        self.status = 'DECLINED'
        self.responded_at = timezone.now()
        self.save()
        return True, "Invitation declined"
    
    @property
    def is_expired(self):
        """Check if invitation has expired."""
        return timezone.now() > self.expires_at
    
    def expire_if_needed(self):
        """Mark invitation as expired if past expiry date."""
        if self.is_expired and self.status == 'PENDING':
            self.status = 'EXPIRED'
            self.save(update_fields=['status'])