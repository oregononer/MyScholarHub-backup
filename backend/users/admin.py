from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, ApplicantProfile, AuditLog


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('username', 'email')
    list_filter = ('role', 'is_staff', 'is_active')
    ordering = ('-date_joined',)

    fieldsets = UserAdmin.fieldsets + (
        ('ScholarHub Info', {'fields': ('role', 'profile_picture')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('ScholarHub Info', {'fields': ('role', 'email')}),
    )


@admin.register(ApplicantProfile)
class ApplicantProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'education_level', 'current_institution', 'major')
    search_fields = ('user__username', 'full_name', 'current_institution')
    list_filter = ('education_level',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Audit Log — INSERT-ONLY.
    TIDAK BOLEH: add, edit, atau delete dari admin panel.
    """
    list_display = ('created_at', 'action_category', 'action_type', 'action_status', 'user', 'ip_address')
    list_filter = ('action_category', 'action_status', 'created_at')
    search_fields = ('user__username', 'action_type', 'ip_address')
    readonly_fields = (
        'id', 'user', 'session_id', 'action_category', 'action_type',
        'target_table', 'target_id', 'action_status', 'payload',
        'ip_address', 'user_agent', 'created_at'
    )
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False  # Tidak bisa tambah log manual

    def has_change_permission(self, request, obj=None):
        return False  # Tidak bisa edit log

    def has_delete_permission(self, request, obj=None):
        return False  # INSERT-ONLY — DILARANG hapus log