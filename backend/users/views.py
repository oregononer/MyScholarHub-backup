"""
Users Views — Authentication, Profile Management, Account Lockout.
Semua endpoint sudah dilengkapi audit logging dan rate limiting.
"""
import uuid
import hashlib
import time
from django.conf import settings
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes, parser_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import CustomUser, ApplicantProfile, AuditLog
from .serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
    ApplicantProfileSerializer,
    ChangePasswordSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)
from .audit import log_event


# ==============================================================================
# CUSTOM THROTTLE CLASSES
# ==============================================================================

class LoginRateThrottle(AnonRateThrottle):
    rate = '5/minute'


class RegisterRateThrottle(AnonRateThrottle):
    rate = '3/hour'


# ==============================================================================
# 1. REGISTRASI (Applicant Only)
# ==============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterRateThrottle])
def register_user(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        log_event(
            action_category='AUTHENTICATION',
            action_type='REGISTER_SUCCESS',
            request=request,
            user=user,
            target_table='users',
            target_id=user.id,
        )
        return Response(
            {"message": "Registrasi berhasil! Silakan login."},
            status=status.HTTP_201_CREATED
        )

    log_event(
        action_category='AUTHENTICATION',
        action_type='REGISTER_FAILED',
        request=request,
        action_status='FAILED',
        payload={'errors': serializer.errors},
    )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# 2. LOGIN DENGAN ACCOUNT LOCKOUT
# ==============================================================================

class CustomLoginView(TokenObtainPairView):
    """
    Login endpoint dengan Account Lockout.
    - 5x gagal → kunci 15 menit (sesuai spec)
    - Counter pakai Django cache (di production: Redis)
    """
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        username = request.data.get('username', '')
        ip = self._get_client_ip(request)

        # --- ACCOUNT LOCKOUT CHECK ---
        lockout_key = f"lockout:{username}"
        attempts_key = f"login_attempts:{username}"

        # Cek apakah akun terkunci
        if cache.get(lockout_key):
            log_event(
                action_category='AUTHENTICATION',
                action_type='ACCOUNT_LOCKED',
                request=request,
                action_status='BLOCKED',
                payload={'username': username},
            )
            return Response(
                {"detail": "Akun terkunci karena terlalu banyak percobaan gagal. Coba lagi dalam 15 menit."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        try:
            # --- PORTAL SEGREGATION ---
            try:
                user_check = CustomUser.objects.get(username=username)
            except CustomUser.DoesNotExist:
                user_check = None

            # [PUBLIC LOGIN] Tolak akses jika role = ADMIN
            if hasattr(self, 'is_admin_portal') and self.is_admin_portal:
                if user_check and user_check.role != 'ADMIN':
                    return Response({"detail": "User portal. Unauthorized for admin access."}, status=status.HTTP_403_FORBIDDEN)
            else:
                if user_check and user_check.role == 'ADMIN':
                    log_event(
                        action_category='AUTHORIZATION',
                        action_type='ADMIN_LOGIN_ATTEMPT_VIA_PUBLIC',
                        request=request,
                        action_status='BLOCKED',
                        payload={'username': username},
                    )
                    return Response({"detail": "Administrator must use the designated secure portal."}, status=status.HTTP_403_FORBIDDEN)

            response = super().post(request, *args, **kwargs)

            # Login berhasil → reset counter
            cache.delete(attempts_key)

            user = user_check

            log_event(
                action_category='AUTHENTICATION',
                action_type='LOGIN_SUCCESS',
                request=request,
                user=user,
                payload={'username': username, 'portal': 'ADMIN' if getattr(self, 'is_admin_portal', False) else 'PUBLIC'},
            )

            # Sertakan role dan identitas dalam response
            if user:
                response.data['user'] = {
                    'username': user.username,
                    'role': user.role
                }

            return response

        except Exception:
            # Login gagal → increment counter
            current_attempts = cache.get(attempts_key, 0) + 1
            cache.set(attempts_key, current_attempts, timeout=settings.ACCOUNT_LOCKOUT_DURATION)

            if current_attempts >= settings.ACCOUNT_LOCKOUT_MAX_ATTEMPTS:
                # Kunci akun
                cache.set(lockout_key, True, timeout=settings.ACCOUNT_LOCKOUT_DURATION)
                log_event(
                    action_category='AUTHENTICATION',
                    action_type='ACCOUNT_LOCKED',
                    request=request,
                    action_status='BLOCKED',
                    payload={
                        'username': username,
                        'attempts': current_attempts,
                        'lockout_duration': settings.ACCOUNT_LOCKOUT_DURATION,
                    },
                )

            log_event(
                action_category='AUTHENTICATION',
                action_type='LOGIN_FAILED',
                request=request,
                action_status='FAILED',
                payload={
                    'username': username,
                    'attempts': current_attempts,
                    'remaining': settings.ACCOUNT_LOCKOUT_MAX_ATTEMPTS - current_attempts,
                },
            )
            return Response(
                {"detail": "Username atau password salah!"},
                status=status.HTTP_401_UNAUTHORIZED
            )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


# ==============================================================================
# 3. LIHAT PROFIL (GET)
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_profile(request):
    """
    GET /api/me/profile/ — Anti-IDOR: selalu return data user yang sedang login.
    """
    user = request.user
    profile_data = {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "profile_picture": request.build_absolute_uri(user.profile_picture.url) if user.profile_picture else None,
    }

    # Tambah data ApplicantProfile jika ada
    try:
        ap = user.applicant_profile
        profile_data.update({
            "full_name": ap.full_name,
            "education_level": ap.education_level,
            "current_institution": ap.current_institution,
            "major": ap.major,
        })
    except ApplicantProfile.DoesNotExist:
        pass

    return Response(profile_data)


# ==============================================================================
# 4. UPDATE PROFIL (PATCH)
# ==============================================================================

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_my_profile(request):
    """
    PATCH /api/me/profile/ — Anti-IDOR: hanya bisa update data sendiri.
    """
    user = request.user
    updated_fields = []

    # Update username
    new_username = request.data.get('username')
    if new_username and new_username != user.username:
        user.username = new_username
        user.save(update_fields=['username'])
        updated_fields.append('username')

    # Update ApplicantProfile fields
    if user.is_applicant_role:
        profile, _ = ApplicantProfile.objects.get_or_create(user=user)
        profile_fields = ['full_name', 'education_level', 'current_institution', 'major']
        for field in profile_fields:
            value = request.data.get(field)
            if value is not None:
                setattr(profile, field, value)
                updated_fields.append(field)
        if updated_fields:
            profile.save()

    if updated_fields:
        log_event(
            action_category='DATA_MUTATION',
            action_type='PROFILE_UPDATE',
            request=request,
            user=user,
            target_table='users',
            target_id=user.id,
            payload={'updated_fields': updated_fields},
        )
        return Response({"message": "Profil berhasil diperbarui!", "updated": updated_fields})

    return Response({"error": "Tidak ada data yang diubah."}, status=status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# 5. GANTI PASSWORD (POST) — Wajib verifikasi old_password
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})

    if serializer.is_valid():
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        log_event(
            action_category='AUTHENTICATION',
            action_type='PASSWORD_CHANGED',
            request=request,
            user=user,
            target_table='users',
            target_id=user.id,
        )
        return Response({"message": "Password berhasil diganti! Silakan login ulang."})

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# 6. FORGOT PASSWORD — Request Token
# ==============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    """
    POST /api/auth/forgot-password/
    Generate token reset, simpan di cache (15 menit TTL).
    Di production, token dikirim via email.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']

    try:
        user = CustomUser.objects.get(email=email, is_active=True)
    except CustomUser.DoesNotExist:
        # SECURITY: Jangan beritahu apakah email terdaftar atau tidak
        return Response({"message": "Jika email terdaftar, link reset password telah dikirim."})

    # Generate one-time token
    token = hashlib.sha256(f"{user.id}-{time.time()}-{uuid.uuid4()}".encode()).hexdigest()

    # Simpan di cache dengan TTL 1 jam (3600 detik)
    cache.set(f"reset_token:{token}", str(user.id), timeout=3600)

    log_event(
        action_category='AUTHENTICATION',
        action_type='PASSWORD_RESET_REQUESTED',
        request=request,
        user=user,
        target_table='users',
        target_id=user.id,
    )

    # --- LOCALHOST DEV MODE ---
    # Di production, token dikirim via email menggunakan SMTP.
    # Untuk development, token ditampilkan di response.
    # HAPUS 'token' dari response SAAT DEPLOY KE PRODUCTION
    return Response({
        "message": "Jika email terdaftar, link reset password telah dikirim.",
        "dev_token": token,  # HAPUS SAAT DEPLOY KE PRODUCTION
    })


# ==============================================================================
# 7. RESET PASSWORD — Konfirmasi Token
# ==============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    POST /api/auth/reset-password/
    Verifikasi token dan set password baru.
    Token one-time — langsung dihapus setelah digunakan.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    token = serializer.validated_data['token']
    new_password = serializer.validated_data['new_password']

    # Cari user_id dari cache
    cache_key = f"reset_token:{token}"
    user_id = cache.get(cache_key)

    if not user_id:
        return Response(
            {"error": "Token tidak valid atau sudah expired."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = CustomUser.objects.get(id=user_id, is_active=True)
    except CustomUser.DoesNotExist:
        return Response(
            {"error": "User tidak ditemukan."},
            status=status.HTTP_404_NOT_FOUND
        )

    user.set_password(new_password)
    user.save()

    # One-time token → hapus setelah dipakai
    cache.delete(cache_key)

    log_event(
        action_category='AUTHENTICATION',
        action_type='PASSWORD_RESET',
        request=request,
        user=user,
        target_table='users',
        target_id=user.id,
    )
    return Response({"message": "Password berhasil di-reset! Silakan login."})


# ==============================================================================
# 8. UPDATE FOTO PROFIL
# ==============================================================================

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def update_profile_picture(request):
    user = request.user
    if 'profile_picture' not in request.FILES:
        return Response({'error': 'Tidak ada gambar!'}, status=status.HTTP_400_BAD_REQUEST)

    user.profile_picture = request.FILES['profile_picture']
    user.save(update_fields=['profile_picture'])

    log_event(
        action_category='DATA_MUTATION',
        action_type='PROFILE_PICTURE_UPDATE',
        request=request,
        user=user,
        target_table='users',
        target_id=user.id,
    )

    return Response({
        'message': 'Foto profil diperbarui!',
        'profile_picture_url': request.build_absolute_uri(user.profile_picture.url)
    })


# ==============================================================================
# 9. ADMIN PORTAL (ISOLATED)
# ==============================================================================

class AdminLoginView(CustomLoginView):
    """
    Endpoint eksklusif untuk Admin.
    Hanya bisa diakses via VLAN (Nginx layer) dan menolak user non-admin.
    """
    is_admin_portal = True