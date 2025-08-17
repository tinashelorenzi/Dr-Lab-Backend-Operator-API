# samples/models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid
import random
import string
from datetime import datetime, timedelta

User = get_user_model()


class Client(models.Model):
    """Client/Customer model for managing contracted clients."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Client company name")
    contact_person = models.CharField(max_length=255, blank=True, help_text="Primary contact person")
    email = models.EmailField(help_text="Primary contact email")
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    
    # Client type and status
    client_type = models.CharField(
        max_length=20,
        choices=[
            ('CONTRACTED', 'Contracted Client'),
            ('ONE_TIME', 'One-time Client'),
            ('LONG_TERM', 'Long-term Client'),
        ],
        default='ONE_TIME'
    )
    is_active = models.BooleanField(default=True)
    
    # SLA and billing information
    default_sla_hours = models.PositiveIntegerField(
        default=72, 
        help_text="Default Service Level Agreement in hours"
    )
    billing_contact = models.CharField(max_length=255, blank=True)
    billing_email = models.EmailField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_clients'
    )
    
    class Meta:
        db_table = 'clients'
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_client_type_display()})"


class Project(models.Model):
    """Project model for grouping samples under specific projects."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Project name")
    description = models.TextField(blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='projects')
    
    # Project status
    status = models.CharField(
        max_length=20,
        choices=[
            ('ACTIVE', 'Active'),
            ('COMPLETED', 'Completed'),
            ('ON_HOLD', 'On Hold'),
            ('CANCELLED', 'Cancelled'),
        ],
        default='ACTIVE'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_projects'
    )
    
    class Meta:
        db_table = 'projects'
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.client.name}"


class SampleBatch(models.Model):
    """Batch model for grouping samples - generates single test report per client."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch_number = models.CharField(max_length=50, unique=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='batches')
    project = models.ForeignKey(
        Project, 
        on_delete=models.CASCADE, 
        related_name='batches',
        null=True, 
        blank=True
    )
    
    # Testing department assignment
    testing_department = models.CharField(
        max_length=20,
        choices=[
            ('CHEMISTRY', 'Chemistry'),
            ('MICROBIOLOGY', 'Microbiology'),
            ('METALS', 'Metals'),
        ],
        help_text="Client decides: micro or chem (or metals)"
    )
    
    # SLA tracking
    sla_hours = models.PositiveIntegerField(help_text="Service Level Agreement in hours")
    due_date = models.DateTimeField(help_text="When batch is due based on SLA")
    
    # Batch status
    status = models.CharField(
        max_length=20,
        choices=[
            ('RECEIVED', 'Received'),
            ('IN_PROGRESS', 'In Progress'),
            ('TESTING', 'Testing'),
            ('REVIEW', 'Under Review'),
            ('COMPLETED', 'Completed'),
            ('DELIVERED', 'Delivered'),
        ],
        default='RECEIVED'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_batches'
    )
    
    class Meta:
        db_table = 'sample_batches'
        verbose_name = 'Sample Batch'
        verbose_name_plural = 'Sample Batches'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.batch_number:
            self.batch_number = self.generate_batch_number()
        if not self.due_date and self.sla_hours:
            self.due_date = timezone.now() + timedelta(hours=self.sla_hours)
        super().save(*args, **kwargs)
    
    def generate_batch_number(self):
        """Generate unique batch number."""
        year = datetime.now().year
        # Get count of batches this year for sequence
        year_count = SampleBatch.objects.filter(
            created_at__year=year
        ).count() + 1
        return f"B-{year}-{year_count:04d}"
    
    def __str__(self):
        return f"{self.batch_number} - {self.client.name}"


class Sample(models.Model):
    """Main Sample model with all tracking requirements from meeting notes."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sample_id = models.CharField(max_length=50, unique=True, editable=False)
    barcode = models.CharField(max_length=100, unique=True, editable=False)
    
    # Batch and client relationship
    batch = models.ForeignKey(SampleBatch, on_delete=models.CASCADE, related_name='samples')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='samples')
    project = models.ForeignKey(
        Project, 
        on_delete=models.CASCADE, 
        related_name='samples',
        null=True, 
        blank=True
    )
    
    # Sample specifications
    volume_ml = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Sample volume in ml (minimum 1000ml required)"
    )
    sample_type = models.CharField(
        max_length=100,
        help_text="Type of sample (e.g., water, soil, blood, etc.)"
    )
    description = models.TextField(blank=True, help_text="Additional sample description")
    
    # Sample conditions upon receipt
    temperature_on_receipt = models.CharField(max_length=50, blank=True)
    condition_notes = models.TextField(
        blank=True, 
        help_text="Record sample conditions on arrival"
    )
    storage_requirement = models.CharField(
        max_length=50,
        choices=[
            ('FROZEN', 'Frozen (Recommended)'),
            ('REFRIGERATED', 'Refrigerated'),
            ('ROOM_TEMP', 'Room Temperature'),
            ('SPECIAL', 'Special Storage'),
        ],
        default='FROZEN'
    )
    
    # Department assignment (from batch, but can be overridden)
    assigned_department = models.CharField(
        max_length=20,
        choices=[
            ('CHEMISTRY', 'Chemistry'),
            ('MICROBIOLOGY', 'Microbiology'),
            ('METALS', 'Metals'),
        ]
    )
    
    # Sample status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('RECEIVED', 'Received'),
            ('REGISTERED', 'Registered'),
            ('QUEUED', 'Queued for Testing'),
            ('TESTING', 'Under Testing'),
            ('VERIFICATION', 'Verification in Progress'),
            ('COMPLETED', 'Testing Completed'),
            ('DISCARDED', 'Discarded'),
        ],
        default='RECEIVED'
    )
    
    # Sample lifecycle dates
    received_at = models.DateTimeField(auto_now_add=True)
    testing_started_at = models.DateTimeField(null=True, blank=True)
    testing_completed_at = models.DateTimeField(null=True, blank=True)
    discard_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Samples discarded after 2 weeks"
    )
    
    # Quality and validation
    requires_verification = models.BooleanField(
        default=True,
        help_text="Verification should be possible in between"
    )
    verification_completed = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_samples'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    received_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='received_samples'
    )
    
    class Meta:
        db_table = 'samples'
        verbose_name = 'Sample'
        verbose_name_plural = 'Samples'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['sample_id']),
            models.Index(fields=['barcode']),
            models.Index(fields=['status']),
            models.Index(fields=['assigned_department']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.sample_id:
            self.sample_id = self.generate_sample_id()
        if not self.barcode:
            self.barcode = self.generate_barcode()
        if not self.discard_date:
            # Samples discarded after 2 weeks
            self.discard_date = timezone.now() + timedelta(weeks=2)
        if not self.assigned_department and self.batch:
            self.assigned_department = self.batch.testing_department
        super().save(*args, **kwargs)
    
    def generate_sample_id(self):
        """Generate unique sample ID."""
        year = datetime.now().year
        # Get count of samples this year for sequence
        year_count = Sample.objects.filter(
            received_at__year=year
        ).count() + 1
        return f"S-{year}-{year_count:06d}"
    
    def generate_barcode(self):
        """Generate unique barcode."""
        # Generate a unique barcode with prefix
        timestamp = int(timezone.now().timestamp())
        random_suffix = ''.join(random.choices(string.digits, k=4))
        return f"DRLB{timestamp}{random_suffix}"
    
    @property
    def is_overdue(self):
        """Check if sample is overdue for discard."""
        return timezone.now() > self.discard_date if self.discard_date else False
    
    @property
    def days_until_discard(self):
        """Calculate days until sample should be discarded."""
        if self.discard_date:
            delta = self.discard_date - timezone.now()
            return max(0, delta.days)
        return 0
    
    def can_be_verified(self):
        """Check if sample can be verified based on current status."""
        return self.status in ['TESTING', 'COMPLETED'] and not self.verification_completed
    
    def mark_for_discard(self):
        """Mark sample for discard if past retention period."""
        if self.is_overdue and self.status != 'DISCARDED':
            self.status = 'DISCARDED'
            self.save(update_fields=['status', 'updated_at'])
    
    def __str__(self):
        return f"{self.sample_id} - {self.client.name}"


class SampleWorksheet(models.Model):
    """Worksheet model - Units can fill-in the same worksheet."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    worksheet_number = models.CharField(max_length=50, unique=True, editable=False)
    samples = models.ManyToManyField(Sample, related_name='worksheets')
    department = models.CharField(
        max_length=20,
        choices=[
            ('CHEMISTRY', 'Chemistry'),
            ('MICROBIOLOGY', 'Microbiology'), 
            ('METALS', 'Metals'),
        ]
    )
    
    # Worksheet status
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('ACTIVE', 'Active'),
            ('IN_PROGRESS', 'In Progress'),
            ('COMPLETED', 'Completed'),
            ('REVIEWED', 'Reviewed'),
        ],
        default='DRAFT'
    )
    
    # Timestamps and assignments
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_worksheets'
    )
    assigned_technicians = models.ManyToManyField(
        User,
        related_name='assigned_worksheets',
        blank=True,
        help_text="Units can fill-in the same worksheet"
    )
    
    class Meta:
        db_table = 'sample_worksheets'
        verbose_name = 'Sample Worksheet'
        verbose_name_plural = 'Sample Worksheets'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.worksheet_number:
            self.worksheet_number = self.generate_worksheet_number()
        super().save(*args, **kwargs)
    
    def generate_worksheet_number(self):
        """Generate unique worksheet number."""
        year = datetime.now().year
        dept_prefix = self.department[:4].upper()  # CHEM, MICR, META
        year_count = SampleWorksheet.objects.filter(
            created_at__year=year,
            department=self.department
        ).count() + 1
        return f"WS-{dept_prefix}-{year}-{year_count:04d}"
    
    def __str__(self):
        return f"{self.worksheet_number} - {self.get_department_display()}"