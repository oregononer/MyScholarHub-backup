import uuid
from django.db import models
from django.conf import settings
from slugify import slugify


class Category(models.Model):
    """
    Kategori Beasiswa — sesuai spec tabel `scholarship_categories`.
    Slug di-generate otomatis dari nama, tidak ada input manual untuk slug.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'scholarship_categories'
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        # Auto-generate slug dari name — tidak boleh manual input
        if not self.slug or self._slug_needs_update():
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def _slug_needs_update(self):
        """Cek apakah slug perlu di-update karena name berubah."""
        if self.pk:
            try:
                old = Category.objects.get(pk=self.pk)
                return old.name != self.name
            except Category.DoesNotExist:
                return True
        return True

    def __str__(self):
        return self.name


class Scholarship(models.Model):
    """
    Model utama Beasiswa — sesuai spec tabel `scholarships`.
    ID (UUIDv4) juga berfungsi sebagai Tracking ID Provider.
    """
    COVERAGE_CHOICES = (
        ('FULL_FUNDED', 'Full Funded'),
        ('PARTIAL_FUNDED', 'Partial Funded'),
        ('ALLOWANCE_ONLY', 'Allowance Only'),
    )

    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending'),
        ('PUBLISHED', 'Published'),
        ('REJECTED', 'Rejected'),
    )

    EDUCATION_LEVEL_CHOICES = (
        ('SMA/SMK', 'SMA/SMK'),
        ('D3', 'D3'),
        ('D4/S1', 'D4/S1'),
        ('S2', 'S2'),
        ('S3', 'S3'),
        ('Lainnya', 'Lainnya'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,  # RESTRICT: tidak boleh hapus kategori yang masih dipakai
        null=True,
        related_name='scholarships'
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    provider_name = models.CharField(max_length=255)
    provider_email = models.EmailField(max_length=255)
    education_level = models.CharField(
        max_length=20,
        choices=EDUCATION_LEVEL_CHOICES,
        blank=True
    )
    coverage_type = models.CharField(
        max_length=20,
        choices=COVERAGE_CHOICES,
        default='FULL_FUNDED'
    )
    description = models.TextField()       # Disanitasi bleach sebelum disimpan
    requirements = models.TextField(blank=True, default='')  # Disanitasi bleach
    external_link = models.URLField(max_length=2048)  # Divalidasi regex, hanya http/https
    poster = models.ImageField(upload_to='scholarship_posters/', null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    rejection_reason = models.CharField(max_length=500, blank=True, default='')
    deadline = models.DateField()
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_scholarships'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='submitted_scholarships'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scholarships'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'deadline']),
        ]

    def save(self, *args, **kwargs):
        # Auto-generate slug dari title
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Scholarship.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.status})"


class Bookmark(models.Model):
    """
    Bookmark/Simpanan Beasiswa — sesuai spec tabel `user_bookmarks`.
    Composite unique constraint: satu user tidak bisa bookmark beasiswa yang sama 2x.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookmarks'
    )
    scholarship = models.ForeignKey(
        Scholarship,
        on_delete=models.CASCADE,
        related_name='bookmarked_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_bookmarks'
        unique_together = ('user', 'scholarship')

    def __str__(self):
        return f"{self.user.username} → {self.scholarship.title}"