"""
Scholarship Serializers — Dual Serializer (Public vs Detail).
Implementasi bleach sanitasi untuk field rich-text.
"""
import bleach
from django.conf import settings
from rest_framework import serializers
from .models import Category, Scholarship, Bookmark


# ==============================================================================
# SANITASI HTML — Utility
# ==============================================================================

def sanitize_html(value):
    """Sanitasi HTML menggunakan bleach. Hanya tag yang diizinkan yang lolos."""
    if not value:
        return value
    return bleach.clean(
        value,
        tags=settings.BLEACH_ALLOWED_TAGS,
        attributes=settings.BLEACH_ALLOWED_ATTRIBUTES,
        strip=settings.BLEACH_STRIP,
    )


def validate_external_link(value):
    """Validasi URL — hanya http/https yang diterima."""
    if not value:
        return value

    # Cek skema yang diblokir
    value_lower = value.lower().strip()
    for scheme in settings.BLOCKED_URL_SCHEMES:
        if value_lower.startswith(scheme):
            raise serializers.ValidationError(
                f"URL dengan skema '{scheme}' tidak diizinkan. Gunakan http:// atau https://"
            )

    # Validasi format URL
    if not settings.URL_VALIDATION_REGEX.match(value):
        raise serializers.ValidationError(
            "Format URL tidak valid. URL harus diawali dengan http:// atau https://"
        )

    return value


def validate_provider_email(value):
    """Validasi format email provider — wajib format valid dan domain nyata."""
    if not value:
        return value

    import re
    # Regex email standar RFC 5322 (simplified)
    email_regex = re.compile(
        r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    )
    if not email_regex.match(value.strip()):
        raise serializers.ValidationError(
            'Format email tidak valid. Contoh: provider@universitas.ac.id'
        )

    # Blokir karakter berbahaya yang bisa lolos regex sederhana
    if any(c in value for c in ['<', '>', '"', "'", ';', '(', ')']):
        raise serializers.ValidationError(
            'Email mengandung karakter yang tidak diizinkan.'
        )

    return value.strip().lower()


# ==============================================================================
# CATEGORY SERIALIZER
# ==============================================================================

class CategorySerializer(serializers.ModelSerializer):
    scholarship_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'is_active', 'scholarship_count')
        read_only_fields = ('slug',)  # Slug auto-generated dari name

    def get_scholarship_count(self, obj):
        return obj.scholarships.filter(status='PUBLISHED').count()


# ==============================================================================
# SCHOLARSHIP SERIALIZERS — Dual (Public vs Detail)
# ==============================================================================

class PublicScholarshipSerializer(serializers.ModelSerializer):
    """
    Serializer untuk Guest / Public.
    TIDAK menyertakan: external_link, requirements (detail).
    Hanya menampilkan info dasar untuk katalog.
    """
    category_name = serializers.ReadOnlyField(source='category.name')
    category_slug = serializers.ReadOnlyField(source='category.slug')

    class Meta:
        model = Scholarship
        fields = (
            'id', 'title', 'slug', 'provider_name', 'deadline',
            'category', 'category_name', 'category_slug',
            'education_level', 'coverage_type', 'poster',
            'created_at',
        )
        # PENTING: external_link TIDAK ADA di list ini


class DetailScholarshipSerializer(serializers.ModelSerializer):
    """
    Serializer untuk Applicant (authenticated).
    Menyertakan semua field termasuk external_link dan requirements.
    """
    category_name = serializers.ReadOnlyField(source='category.name')
    category_slug = serializers.ReadOnlyField(source='category.slug')
    is_bookmarked = serializers.SerializerMethodField()
    is_match = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Scholarship
        fields = (
            'id', 'title', 'slug', 'provider_name', 'provider_email',
            'deadline', 'category', 'category_name', 'category_slug',
            'education_level', 'coverage_type', 'description',
            'requirements', 'external_link', 'poster', 'status',
            'created_at', 'updated_at', 'is_bookmarked', 'is_match',
        )

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Bookmark.objects.filter(
                user=request.user,
                scholarship=obj
            ).exists()
        return False


class ScholarshipCreateSerializer(serializers.ModelSerializer):
    """
    Serializer untuk membuat/edit beasiswa (Admin atau Provider submission).
    Melakukan sanitasi HTML pada description dan requirements.
    Melakukan validasi URL pada external_link.
    Melakukan validasi format email provider.
    """
    class Meta:
        model = Scholarship
        fields = (
            'title', 'category', 'provider_name', 'provider_email',
            'education_level', 'coverage_type', 'description',
            'requirements', 'external_link', 'deadline', 'poster',
        )

    def validate_description(self, value):
        """Sanitasi HTML — cegah Stored XSS."""
        return sanitize_html(value)

    def validate_requirements(self, value):
        """Sanitasi HTML — cegah Stored XSS."""
        return sanitize_html(value)

    def validate_external_link(self, value):
        """Validasi URL — tolak javascript:, data:, vbscript:, ftp://"""
        return validate_external_link(value)

    def validate_provider_email(self, value):
        """Validasi format email provider — wajib format yang valid."""
        return validate_provider_email(value)


class ProviderSubmissionSerializer(serializers.ModelSerializer):
    """
    Serializer untuk form pengajuan Provider (multi-step).
    Status otomatis PENDING. provider_email wajib diisi dan valid.
    """
    class Meta:
        model = Scholarship
        fields = (
            'title', 'category', 'provider_name', 'provider_email',
            'education_level', 'coverage_type', 'description',
            'requirements', 'external_link', 'deadline', 'poster',
        )

    def validate_description(self, value):
        return sanitize_html(value)

    def validate_requirements(self, value):
        return sanitize_html(value)

    def validate_external_link(self, value):
        return validate_external_link(value)

    def validate_provider_email(self, value):
        return validate_provider_email(value)


class SubmissionTrackingSerializer(serializers.ModelSerializer):
    """Serializer untuk tracking status pengajuan (public, by UUID)."""
    class Meta:
        model = Scholarship
        fields = ('id', 'status', 'rejection_reason', 'created_at')


# ==============================================================================
# BOOKMARK SERIALIZER
# ==============================================================================

class BookmarkSerializer(serializers.ModelSerializer):
    scholarship_title = serializers.ReadOnlyField(source='scholarship.title')
    scholarship_slug = serializers.ReadOnlyField(source='scholarship.slug')
    scholarship_provider = serializers.ReadOnlyField(source='scholarship.provider_name')
    scholarship_deadline = serializers.ReadOnlyField(source='scholarship.deadline')
    scholarship_poster = serializers.ImageField(source='scholarship.poster', read_only=True)

    class Meta:
        model = Bookmark
        fields = (
            'id', 'scholarship', 'scholarship_title', 'scholarship_slug',
            'scholarship_provider', 'scholarship_deadline', 'scholarship_poster',
            'created_at',
        )
        read_only_fields = ('id', 'created_at')


# ==============================================================================
# ADMIN SERIALIZERS
# ==============================================================================

class AdminScholarshipSerializer(serializers.ModelSerializer):
    """Serializer lengkap untuk Admin (termasuk status, published_by, dll)."""
    category_name = serializers.ReadOnlyField(source='category.name')
    created_by_username = serializers.ReadOnlyField(source='created_by.username')
    published_by_username = serializers.ReadOnlyField(source='published_by.username')

    class Meta:
        model = Scholarship
        fields = '__all__'
        read_only_fields = ('id', 'slug', 'created_at', 'updated_at', 'created_by', 'published_by')

    def validate_description(self, value):
        return sanitize_html(value)

    def validate_requirements(self, value):
        return sanitize_html(value)

    def validate_external_link(self, value):
        return validate_external_link(value)


class ModerationActionSerializer(serializers.Serializer):
    """Serializer untuk aksi moderasi (reject dengan alasan)."""
    rejection_reason = serializers.CharField(max_length=500, required=True)