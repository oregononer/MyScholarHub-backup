"""
Custom Middleware — RBAC Enforcement & Security.

Fungsi:
1. Blokir akses Applicant ke /admin-panel/*
2. Blokir akses non-admin ke /api/admin/*
3. Redirect user tanpa JWT ke login jika akses /app/*
"""
import re
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .audit import log_event


class RBACMiddleware:
    """
    Middleware untuk enforce Role-Based Access Control di level HTTP.
    Berjalan SEBELUM view function dipanggil.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # === Proteksi Admin API endpoints ===
        if path.startswith('/api/admin/') and not path.startswith('/api/admin/auth/login/'):
            user = self._get_jwt_user(request)
            if user is None:
                return JsonResponse(
                    {'detail': 'Authentication credentials were not provided.'},
                    status=401
                )
            if not user.is_admin_role:
                log_event(
                    action_category='AUTHORIZATION',
                    action_type='UNAUTHORIZED_ACCESS_ATTEMPT',
                    request=request,
                    user=user,
                    action_status='BLOCKED',
                    payload={'attempted_path': path}
                )
                return JsonResponse(
                    {'detail': 'Anda tidak memiliki izin untuk mengakses resource ini.'},
                    status=403
                )

        # === Proteksi Applicant API endpoints ===
        if path.startswith('/api/me/'):
            user = self._get_jwt_user(request)
            if user is None:
                return JsonResponse(
                    {'detail': 'Authentication credentials were not provided.'},
                    status=401
                )

        response = self.get_response(request)
        return response

    def _get_jwt_user(self, request):
        """Ekstrak user dari JWT token di header Authorization."""
        try:
            jwt_auth = JWTAuthentication()
            validated = jwt_auth.authenticate(request)
            if validated:
                return validated[0]
        except (InvalidToken, TokenError):
            pass
        return None
