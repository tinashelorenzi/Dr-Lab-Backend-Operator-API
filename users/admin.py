from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.core.exceptions import ValidationError
from django import forms
from django.utils.html import format_html
from django.utils import timezone
from .models import User, UserSession


class UserCreationForm(forms.ModelForm):
    """A form for creating new users. Includes all the required
    fields, plus a repeated password."""
    
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'tel', 'role')

    def clean_password2(self):
        # Check that the two password entries match
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        # Save the provided password in hashed format
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    """A form for updating users. Includes all the fields on
    the user, but replaces the password field with admin's
    disabled password hash display field."""
    
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'tel', 'role', 
                 'is_active', 'is_staff', 'is_superuser')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for the User model."""
    
    # The forms to add and change user instances
    form = UserChangeForm
    add_form = UserCreationForm

    # The fields to be used in displaying the User model.
    list_display = ('email', 'get_full_name', 'role', 'is_active', 'is_online_status', 
                   'last_login', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'role', 'date_joined')
    
    # Fields for the user detail page
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'tel')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'role', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined', 'last_ping'),
            'classes': ('collapse',)
        }),
        ('Security Keys', {
            'fields': ('public_key', 'private_key'),
            'classes': ('collapse',),
            'description': 'RSA key pair for secure operations. Private key should be kept confidential.'
        }),
    )
    
    # Fields for the add user page
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'tel', 'role', 
                      'password1', 'password2', 'is_active', 'is_staff'),
        }),
    )
    
    # Search and ordering
    search_fields = ('email', 'first_name', 'last_name', 'tel')
    ordering = ('email',)
    filter_horizontal = ('groups', 'user_permissions')
    
    # Read-only fields
    readonly_fields = ('date_joined', 'last_login', 'last_ping', 'id')
    
    # Custom methods for list display
    def get_full_name(self, obj):
        """Display the full name of the user."""
        return obj.get_full_name()
    get_full_name.short_description = 'Full Name'
    
    def is_online_status(self, obj):
        """Display online status with colored indicator."""
        if obj.is_online():
            return format_html(
                '<span style="color: green;">●</span> Online'
            )
        else:
            return format_html(
                '<span style="color: red;">●</span> Offline'
            )
    is_online_status.short_description = 'Status'
    is_online_status.allow_tags = True
    
    # Custom actions
    actions = ['activate_users', 'deactivate_users', 'generate_keys_for_users', 'ping_users']
    
    def activate_users(self, request, queryset):
        """Activate selected users."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users have been activated.')
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users have been deactivated.')
    deactivate_users.short_description = "Deactivate selected users"
    
    def generate_keys_for_users(self, request, queryset):
        """Generate RSA key pairs for selected users."""
        count = 0
        for user in queryset:
            user.generate_key_pair()
            count += 1
        self.message_user(request, f'Generated key pairs for {count} users.')
    generate_keys_for_users.short_description = "Generate RSA keys for selected users"
    
    def ping_users(self, request, queryset):
        """Update last ping for selected users."""
        for user in queryset:
            user.update_last_ping()
        self.message_user(request, f'Updated ping timestamp for {queryset.count()} users.')
    ping_users.short_description = "Update ping timestamp for selected users"
    
    # Override save methods to handle key generation
    def save_model(self, request, obj, form, change):
        """Override save to automatically generate keys if needed."""
        super().save_model(request, obj, form, change)
        
        # Generate keys if they don't exist
        if not obj.private_key or not obj.public_key:
            obj.generate_key_pair()
            self.message_user(request, f'Generated RSA key pair for {obj.email}.')


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Admin interface for the UserSession model."""
    
    list_display = ('user', 'session_key_short', 'ip_address', 'is_active', 
                   'created_at', 'last_activity', 'session_duration')
    list_filter = ('is_active', 'created_at', 'last_activity')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 
                    'ip_address', 'session_key')
    readonly_fields = ('id', 'session_key', 'created_at', 'last_activity', 'session_duration')
    ordering = ('-last_activity',)
    
    # Custom display methods
    def session_key_short(self, obj):
        """Display shortened session key."""
        return f"{obj.session_key[:10]}..."
    session_key_short.short_description = 'Session Key'
    
    def session_duration(self, obj):
        """Calculate and display session duration."""
        if obj.created_at and obj.last_activity:
            duration = obj.last_activity - obj.created_at
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        return "N/A"
    session_duration.short_description = 'Duration'
    
    # Custom actions
    actions = ['deactivate_sessions']
    
    def deactivate_sessions(self, request, queryset):
        """Deactivate selected sessions."""
        for session in queryset:
            session.deactivate()
        self.message_user(request, f'Deactivated {queryset.count()} sessions.')
    deactivate_sessions.short_description = "Deactivate selected sessions"
    
    # Fieldsets for detail view
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'session_key', 'is_active')
        }),
        ('Connection Details', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_activity', 'session_duration'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent manual creation of sessions through admin."""
        return False


# Customize admin site headers
admin.site.site_header = "Dr Lab LIMS Administration"
admin.site.site_title = "Dr Lab LIMS Admin"
admin.site.index_title = "Welcome to Dr Lab LIMS Administration"