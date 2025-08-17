# samples/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Client, Project, SampleBatch, Sample, SampleWorksheet


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'client_type', 'contact_person', 'email', 
        'default_sla_hours', 'is_active', 'created_at'
    ]
    list_filter = ['client_type', 'is_active', 'created_at']
    search_fields = ['name', 'contact_person', 'email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'contact_person', 'email', 'phone', 'address')
        }),
        ('Client Details', {
            'fields': ('client_type', 'is_active', 'default_sla_hours')
        }),
        ('Billing Information', {
            'fields': ('billing_contact', 'billing_email'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new client
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'client', 'status', 'created_at', 'completed_at'
    ]
    list_filter = ['status', 'created_at', 'client']
    search_fields = ['name', 'client__name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Project Information', {
            'fields': ('name', 'description', 'client', 'status')
        }),
        ('Timeline', {
            'fields': ('completed_at',),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new project
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SampleBatch)
class SampleBatchAdmin(admin.ModelAdmin):
    list_display = [
        'batch_number', 'client', 'testing_department', 'status', 
        'sla_hours', 'due_date', 'sample_count', 'created_at'
    ]
    list_filter = ['testing_department', 'status', 'created_at', 'due_date']
    search_fields = ['batch_number', 'client__name', 'project__name']
    readonly_fields = ['batch_number', 'created_at', 'updated_at', 'due_date']
    
    fieldsets = (
        ('Batch Information', {
            'fields': ('batch_number', 'client', 'project', 'testing_department')
        }),
        ('SLA & Timeline', {
            'fields': ('sla_hours', 'due_date', 'status')
        }),
        ('Completion', {
            'fields': ('completed_at',),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def sample_count(self, obj):
        """Display count of samples in this batch."""
        count = obj.samples.count()
        if count > 0:
            url = reverse('admin:samples_sample_changelist') + f'?batch__id__exact={obj.id}'
            return format_html('<a href="{}">{} samples</a>', url, count)
        return '0 samples'
    sample_count.short_description = 'Samples'
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new batch
            obj.created_by = request.user
            if not obj.sla_hours and obj.client:
                obj.sla_hours = obj.client.default_sla_hours
        super().save_model(request, obj, form, change)


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = [
        'sample_id', 'barcode', 'client', 'batch', 'assigned_department',
        'status', 'volume_ml', 'days_remaining', 'received_at'
    ]
    list_filter = [
        'assigned_department', 'status', 'storage_requirement', 
        'verification_completed', 'received_at'
    ]
    search_fields = [
        'sample_id', 'barcode', 'client__name', 'batch__batch_number',
        'sample_type', 'description'
    ]
    readonly_fields = [
        'sample_id', 'barcode', 'created_at', 'updated_at', 
        'discard_date', 'days_remaining_display'
    ]
    
    fieldsets = (
        ('Sample Identification', {
            'fields': ('sample_id', 'barcode', 'batch', 'client', 'project')
        }),
        ('Sample Details', {
            'fields': (
                'volume_ml', 'sample_type', 'description',
                'temperature_on_receipt', 'condition_notes', 'storage_requirement'
            )
        }),
        ('Department & Status', {
            'fields': ('assigned_department', 'status')
        }),
        ('Timeline', {
            'fields': (
                'received_at', 'testing_started_at', 'testing_completed_at',
                'discard_date', 'days_remaining_display'
            ),
            'classes': ('collapse',)
        }),
        ('Verification', {
            'fields': (
                'requires_verification', 'verification_completed',
                'verified_by', 'verified_at'
            ),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('received_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_for_discard', 'bulk_verify', 'move_to_testing']
    
    def days_remaining(self, obj):
        """Display days remaining until discard with color coding."""
        days = obj.days_until_discard
        if days <= 0:
            return format_html('<span style="color: red; font-weight: bold;">OVERDUE</span>')
        elif days <= 3:
            return format_html('<span style="color: orange;">{} days</span>', days)
        else:
            return f'{days} days'
    days_remaining.short_description = 'Days Until Discard'
    
    def days_remaining_display(self, obj):
        """Read-only field showing days remaining."""
        return obj.days_until_discard
    days_remaining_display.short_description = 'Days Until Discard'
    
    def mark_for_discard(self, request, queryset):
        """Admin action to mark samples for discard."""
        updated = 0
        for sample in queryset:
            if sample.is_overdue and sample.status != 'DISCARDED':
                sample.status = 'DISCARDED'
                sample.save(update_fields=['status', 'updated_at'])
                updated += 1
        self.message_user(request, f'Marked {updated} samples for discard.')
    mark_for_discard.short_description = "Mark overdue samples for discard"
    
    def bulk_verify(self, request, queryset):
        """Admin action to bulk verify samples."""
        updated = 0
        for sample in queryset:
            if sample.can_be_verified():
                sample.verification_completed = True
                sample.verified_by = request.user
                sample.verified_at = timezone.now()
                sample.save(update_fields=[
                    'verification_completed', 'verified_by', 'verified_at', 'updated_at'
                ])
                updated += 1
        self.message_user(request, f'Verified {updated} samples.')
    bulk_verify.short_description = "Verify selected samples"
    
    def move_to_testing(self, request, queryset):
        """Admin action to move samples to testing status."""
        updated = queryset.filter(status='QUEUED').update(
            status='TESTING',
            testing_started_at=timezone.now()
        )
        self.message_user(request, f'Moved {updated} samples to testing.')
    move_to_testing.short_description = "Move queued samples to testing"
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new sample
            obj.received_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SampleWorksheet)
class SampleWorksheetAdmin(admin.ModelAdmin):
    list_display = [
        'worksheet_number', 'department', 'status', 
        'sample_count', 'technician_count', 'created_at'
    ]
    list_filter = ['department', 'status', 'created_at']
    search_fields = ['worksheet_number', 'samples__sample_id']
    readonly_fields = ['worksheet_number', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Worksheet Information', {
            'fields': ('worksheet_number', 'department', 'status')
        }),
        ('Assignment', {
            'fields': ('samples', 'assigned_technicians')
        }),
        ('Timeline', {
            'fields': ('completed_at',),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ['samples', 'assigned_technicians']
    
    def sample_count(self, obj):
        """Display count of samples in this worksheet."""
        return obj.samples.count()
    sample_count.short_description = 'Sample Count'
    
    def technician_count(self, obj):
        """Display count of assigned technicians."""
        return obj.assigned_technicians.count()
    technician_count.short_description = 'Technicians'
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new worksheet
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Customize admin site headers for samples
admin.site.site_header = "Dr Lab LIMS - Sample Management"
admin.site.site_title = "Dr Lab LIMS"
admin.site.index_title = "Laboratory Information Management System"