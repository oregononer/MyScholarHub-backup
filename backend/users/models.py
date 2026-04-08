import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Custom User Model — RBAC (Role-Based Access Control)
    Semua PK menggunakan UUIDv4 agar tidak bisa dienumerasi (OWASP).
    """
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('APPLICANT', 'Applicant'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='APPLICANT')
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_admin_role(self):
        return self.role == 'ADMIN'

    @property
    def is_applicant_role(self):
        return self.role == 'APPLICANT'


class ApplicantProfile(models.Model):
    """
    Profil tambahan khusus Applicant — sesuai spec tabel `applicant_profiles`.
    One-to-One dengan CustomUser yang role-nya APPLICANT.
    """
    EDUCATION_LEVEL_CHOICES = (
        ('SMA/SMK', 'SMA/SMK'),
        ('D3', 'D3'),
        ('D4/S1', 'D4/S1'),
        ('S2', 'S2'),
        ('S3', 'S3'),
        ('Lainnya', 'Lainnya'),
    )

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='applicant_profile'
    )
    full_name = models.CharField(max_length=255, blank=True)
    education_level = models.CharField(
        max_length=20,
        choices=EDUCATION_LEVEL_CHOICES,
        blank=True
    )
    current_institution = models.CharField(max_length=255, blank=True)
    major = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'applicant_profiles'

    def __str__(self):
        return f"Profile: {self.user.username}"


class AuditLog(models.Model):
    """
    Audit Log — INSERT-ONLY (tidak boleh UPDATE/DELETE).
    Mencatat semua event keamanan, autentikasi, dan mutasi data.
    """
    ACTION_CATEGORY_CHOICES = (
        ('AUTHENTICATION', 'Authentication'),
        ('AUTHORIZATION', 'Authorization'),
        ('DATA_MUTATION', 'Data Mutation'),
        ('SYSTEM', 'System'),
        ('SECURITY_ANOMALY', 'Security Anomaly'),
    )

    ACTION_STATUS_CHOICES = (
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('BLOCKED', 'Blocked'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs'
    )
    session_id = models.CharField(max_length=100, blank=True, default='')
    action_category = models.CharField(
        max_length=20,
        choices=ACTION_CATEGORY_CHOICES,
        db_index=True
    )
    action_type = models.CharField(max_length=50)  # e.g. LOGIN_SUCCESS, SCHOLARSHIP_APPROVED
    target_table = models.CharField(max_length=50, blank=True, default='')
    target_id = models.CharField(max_length=36, blank=True, default='')
    action_status = models.CharField(
        max_length=10,
        choices=ACTION_STATUS_CHOICES,
        default='SUCCESS',
        db_index=True
    )
    payload = models.JSONField(null=True, blank=True)  # Detail event dalam bentuk JSON
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action_category', 'action_status']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        return f"[{self.created_at}] {self.action_category}/{self.action_type} — {self.action_status}"