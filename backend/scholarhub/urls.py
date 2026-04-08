"""
ScholarHub — Project URL Configuration.
Semua endpoint API diprefix dengan /api/.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView

from users.views import register_user, CustomLoginView, AdminLoginView, forgot_password, reset_password

urlpatterns = [
    # Django default admin (untuk development)
    path('django-admin/', admin.site.urls),

    # === PUBLIC AUTH ENDPOINTS ===
    path('api/auth/register/', register_user, name='register'),
    path('api/auth/login/', CustomLoginView.as_view(), name='login'),
    
    # === ADMIN PORTAL AUTH ENDPOINT (ISOLATED) ===
    path('api/admin/auth/login/', AdminLoginView.as_view(), name='admin_login'),
    
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/forgot-password/', forgot_password, name='forgot_password'),
    path('api/auth/reset-password/', reset_password, name='reset_password'),

    # === USER PROFILE ENDPOINTS (/api/me/*) ===
    path('api/', include('users.urls')),

    # === SCHOLARSHIP, BOOKMARK, ADMIN ENDPOINTS ===
    path('api/', include('scholarships.urls')),
]

# --- LOCALHOST DEV MODE START ---
# HAPUS SAAT DEPLOY KE KUBERNETES: Static/Media files dilayani oleh Nginx
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# --- LOCALHOST DEV MODE END ---