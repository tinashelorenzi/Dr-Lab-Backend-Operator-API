from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Group, GroupMembership, GroupInvitation


class GroupMembershipInline(admin.TabularInline):
    """Inline admin for group memberships."""
    model = GroupMembership
    extra = 0
    readonly_fields = ('id', 'joined_at', 'last_seen')
    fields = ('user', 'role', 'added_by', 'is_muted', 'joined_at', 'last_seen')


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """Admin interface for Group model."""
    
    list_display = ('name', 'group_type', 'member_count_display', 'created_by', 
                   'is_active', 'has_keys_status', 'created_at', 'last_activity')
    list_filter = ('group_type', 'is_active', 'created_at', 'allow_member_invite')
    search_fields = ('name', 'description', 'created_by__email', 'created_by__first_name', 
                    'created_by__last_name')
    readonly_fields = ('id', 'created_at', 'updated_at', 'member_count_display', 'key_info')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'group_type', 'is_active')
        }),
        ('Management', {
            'fields': ('created_by', 'admins', 'max_members', 'allow_member_invite')
        }),
        ('Statistics', {
            'fields': ('member_count_display', 'created_at', 'updated_at', 'last_activity'),
            'classes': ('collapse',)
        }),
        ('Security Keys', {
            'fields': ('key_info', 'public_key'),
            'classes': ('collapse',),
            'description': 'Cryptographic keys for secure group messaging.'
        }),
    )
    
    filter_horizontal = ('admins',)
    inlines = [GroupMembershipInline]
    
    def member_count_display(self, obj):
        """Display member count with max members."""
        count = obj.member_count
        max_count = obj.max_members
        percentage = (count / max_count) * 100 if max_count > 0 else 0
        
        color = 'green' if percentage < 80 else 'orange' if percentage < 95 else 'red'
        
        return format_html(
            '<span style="color: {};">{} / {}</span>',
            color, count, max_count
        )
    member_count_display.short_description = 'Members'
    
    def has_keys_status(self, obj):
        """Display key generation status."""
        if obj.has_keys:
            return format_html(
                '<span style="color: green;">●</span> Keys Generated'
            )
        else:
            return format_html(
                '<span style="color: red;">●</span> No Keys'
            )
    has_keys_status.short_description = 'Keys'
    has_keys_status.allow_tags = True
    
    def key_info(self, obj):
        """Display key information."""
        if obj.has_keys:
            return format_html(
                '<div><strong>Public Key:</strong> Present<br>'
                '<strong>Private Key:</strong> Present<br>'
                '<strong>Key Length:</strong> 2048 bits</div>'
            )
        else:
            return format_html(
                '<div style="color: orange;"><strong>No keys generated</strong><br>'
                'Keys will be generated automatically when group is saved</div>'
            )
    key_info.short_description = 'Key Information'
    key_info.allow_tags = True
    
    actions = ['activate_groups', 'deactivate_groups', 'regenerate_keys']
    
    def activate_groups(self, request, queryset):
        """Activate selected groups."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} groups have been activated.')
    activate_groups.short_description = "Activate selected groups"
    
    def deactivate_groups(self, request, queryset):
        """Deactivate selected groups."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} groups have been deactivated.')
    deactivate_groups.short_description = "Deactivate selected groups"
    
    def regenerate_keys(self, request, queryset):
        """Regenerate keys for selected groups."""
        count = 0
        for group in queryset:
            group.generate_key_pair()
            group.save()
            count += 1
        self.message_user(request, f'Regenerated keys for {count} groups.')
    regenerate_keys.short_description = "Regenerate keys for selected groups"


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    """Admin interface for GroupMembership model."""
    
    list_display = ('user_display', 'group', 'role', 'added_by', 'joined_at', 
                   'last_seen', 'is_muted')
    list_filter = ('role', 'is_muted', 'joined_at', 'group__group_type')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 
                    'group__name', 'added_by__email')
    readonly_fields = ('id', 'joined_at', 'last_seen')
    
    fieldsets = (
        ('Membership Details', {
            'fields': ('group', 'user', 'role', 'added_by')
        }),
        ('Settings', {
            'fields': ('is_muted',)
        }),
        ('Timestamps', {
            'fields': ('joined_at', 'last_seen'),
            'classes': ('collapse',)
        }),
    )
    
    def user_display(self, obj):
        """Display user with full name and email."""
        return f"{obj.user.get_full_name()} ({obj.user.email})"
    user_display.short_description = 'User'
    
    actions = ['update_last_seen', 'mute_members', 'unmute_members']
    
    def update_last_seen(self, request, queryset):
        """Update last seen for selected memberships."""
        for membership in queryset:
            membership.update_last_seen()
        self.message_user(request, f'Updated last seen for {queryset.count()} memberships.')
    update_last_seen.short_description = "Update last seen for selected memberships"
    
    def mute_members(self, request, queryset):
        """Mute selected members."""
        updated = queryset.update(is_muted=True)
        self.message_user(request, f'{updated} members have been muted.')
    mute_members.short_description = "Mute selected members"
    
    def unmute_members(self, request, queryset):
        """Unmute selected members."""
        updated = queryset.update(is_muted=False)
        self.message_user(request, f'{updated} members have been unmuted.')
    unmute_members.short_description = "Unmute selected members"


@admin.register(GroupInvitation)
class GroupInvitationAdmin(admin.ModelAdmin):
    """Admin interface for GroupInvitation model."""
    
    list_display = ('invited_user_display', 'group', 'invited_by', 'status', 
                   'created_at', 'expires_at', 'is_expired_display')
    list_filter = ('status', 'created_at', 'expires_at', 'group__group_type')
    search_fields = ('invited_user__email', 'invited_user__first_name', 
                    'invited_user__last_name', 'group__name', 'invited_by__email')
    readonly_fields = ('id', 'created_at', 'responded_at', 'is_expired_display')
    
    fieldsets = (
        ('Invitation Details', {
            'fields': ('group', 'invited_user', 'invited_by', 'message')
        }),
        ('Status', {
            'fields': ('status', 'expires_at', 'is_expired_display')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'responded_at'),
            'classes': ('collapse',)
        }),
    )
    
    def invited_user_display(self, obj):
        """Display invited user with full name and email."""
        return f"{obj.invited_user.get_full_name()} ({obj.invited_user.email})"
    invited_user_display.short_description = 'Invited User'
    
    def is_expired_display(self, obj):
        """Display expiration status."""
        if obj.is_expired:
            return format_html(
                '<span style="color: red;">●</span> Expired'
            )
        else:
            return format_html(
                '<span style="color: green;">●</span> Valid'
            )
    is_expired_display.short_description = 'Expiry Status'
    is_expired_display.allow_tags = True
    
    actions = ['mark_expired', 'extend_expiry']
    
    def mark_expired(self, request, queryset):
        """Mark selected invitations as expired."""
        for invitation in queryset:
            invitation.expire_if_needed()
        expired_count = queryset.filter(status='EXPIRED').count()
        self.message_user(request, f'{expired_count} invitations marked as expired.')
    mark_expired.short_description = "Mark expired invitations"
    
    def extend_expiry(self, request, queryset):
        """Extend expiry for selected pending invitations by 7 days."""
        pending_invitations = queryset.filter(status='PENDING')
        for invitation in pending_invitations:
            invitation.expires_at = timezone.now() + timezone.timedelta(days=7)
            invitation.save(update_fields=['expires_at'])
        self.message_user(request, f'Extended expiry for {pending_invitations.count()} invitations.')
    extend_expiry.short_description = "Extend expiry by 7 days for pending invitations"