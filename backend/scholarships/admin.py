from django.contrib import admin
from .models import Category, Scholarship, Bookmark


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)
    readonly_fields = ('slug',)  # Slug auto-generated, tidak boleh manual


@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    list_display = ('title', 'provider_name', 'status', 'category', 'coverage_type', 'deadline', 'created_by')
    list_filter = ('status', 'coverage_type', 'category', 'education_level')
    search_fields = ('title', 'provider_name', 'provider_email', 'description')
    readonly_fields = ('id', 'slug', 'created_at', 'updated_at')
    date_hierarchy = 'deadline'

    fieldsets = (
        ('Informasi Utama', {
            'fields': ('id', 'title', 'slug', 'category', 'poster')
        }),
        ('Provider', {
            'fields': ('provider_name', 'provider_email')
        }),
        ('Detail Beasiswa', {
            'fields': ('education_level', 'coverage_type', 'description', 'requirements', 'external_link', 'deadline')
        }),
        ('Status & Moderasi', {
            'fields': ('status', 'rejection_reason', 'published_by', 'created_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'scholarship', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'scholarship__title')
    readonly_fields = ('user', 'scholarship', 'created_at')

    def has_add_permission(self, request):
        return False  # Bookmark hanya via API

    def has_change_permission(self, request, obj=None):
        return False