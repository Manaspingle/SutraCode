import uuid
from django.db import models


class UploadedDocument(models.Model):
    """Stores metadata for uploaded programming documentation (PDF/TXT)."""
    STATUS_CHOICES = [
        ('ready', 'Indexed & Ready'),
        ('processing', 'Processing'),
        ('error', 'Extraction Error'),
        ('empty', 'No Extractable Text'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=128, db_index=True, help_text="Firebase UID or guest session ID")
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512)
    file_type = models.CharField(max_length=10, choices=[('pdf', 'PDF'), ('txt', 'TXT')])
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    page_count = models.PositiveIntegerField(default=1)
    chunk_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    error_message = models.TextField(blank=True, default='')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.filename} ({self.file_type.upper()}) - {self.status}"

    @property
    def file_size_display(self):
        kb = self.file_size / 1024
        if kb < 1024:
            return f"{kb:.1f} KB"
        return f"{kb / 1024:.2f} MB"


class DocumentChunk(models.Model):
    """Individual text passage extracted from a document for vector retrieval."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(UploadedDocument, on_delete=models.CASCADE, related_name='chunks')
    chunk_id = models.CharField(max_length=128, unique=True, db_index=True)
    user_id = models.CharField(max_length=128, db_index=True)
    page_number = models.PositiveIntegerField(null=True, blank=True)
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    char_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'chunk_index']

    def __str__(self):
        return f"{self.document.filename} [Chunk #{self.chunk_index}]"


class AnalysisRecord(models.Model):
    """Analysis record storing diagnosis, reasoning, diff, and citations."""
    STATUS_CHOICES = [
        ('completed', 'Completed with Evidence'),
        ('no_evidence', 'Hypothesis (Insufficient Evidence)'),
        ('failed', 'Analysis Failed'),
    ]

    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('info', 'Informational'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=128, db_index=True)
    language = models.CharField(max_length=50, default='python')
    problem_description = models.TextField()
    error_message = models.TextField(blank=True, default='')
    expected_behavior = models.TextField(blank=True, default='')
    user_question = models.TextField(blank=True, default='')
    submitted_code = models.TextField()

    # Model Diagnosis Outputs
    diagnosis_summary = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    code_observations = models.JSONField(default=list, blank=True)
    root_causes = models.JSONField(default=list, blank=True)
    corrected_code = models.TextField(blank=True, default='')
    change_explanation = models.TextField(blank=True, default='')
    suggested_tests = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=list, blank=True, help_text="Retrieved passages used in synthesis")
    limitations = models.TextField(blank=True, default='')
    is_evidence_backed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.language}] {self.diagnosis_summary[:50]}... ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
