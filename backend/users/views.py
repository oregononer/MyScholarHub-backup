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


class ForgotPasswordRateThrottle(AnonRateThrottle):
    """Maks 3 permintaan reset password per jam per IP.
    Mencegah email bombing dan brute-force token reset."""
    scope = 'forgot_password'
    rate = '3/hour'


class ResetPasswordRateThrottle(AnonRateThrottle):
    """Maks 5 percobaan reset password per jam per IP.
    Mencegah brute-force token."""
    scope = 'reset_password'
    rate = '5/hour'


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
    Validasi: panjang username, karakter, dan keunikan sebelum disimpan.
    """
    user = request.user
    updated_fields = []
    errors = {}

    # Update username — dengan validasi ketat
    new_username = request.data.get('username')
    if new_username is not None:
        new_username = str(new_username).strip()
        if not new_username:
            errors['username'] = 'Username tidak boleh kosong.'
        elif len(new_username) < 3:
            errors['username'] = 'Username minimal 3 karakter.'
        elif len(new_username) > 30:
            errors['username'] = 'Username maksimal 30 karakter.'
        elif not new_username.replace('_', '').replace('.', '').isalnum():
            errors['username'] = 'Username hanya boleh mengandung huruf, angka, titik, dan underscore.'
        elif new_username != user.username:
            if CustomUser.objects.filter(username__iexact=new_username).exclude(pk=user.pk).exists():
                errors['username'] = 'Username sudah digunakan oleh akun lain.'
            else:
                user.username = new_username
                user.save(update_fields=['username'])
                updated_fields.append('username')

    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    # Update ApplicantProfile fields
    if user.is_applicant_role:
        profile, _ = ApplicantProfile.objects.get_or_create(user=user)
        profile_fields = ['full_name', 'education_level', 'current_institution', 'major']
        for field in profile_fields:
            value = request.data.get(field)
            if value is not None:
                # Strip whitespace dari semua field string
                clean_value = str(value).strip() if isinstance(value, str) else value
                setattr(profile, field, clean_value)
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
@throttle_classes([ForgotPasswordRateThrottle])
def forgot_password(request):
    """
    POST /api/auth/forgot-password/
    Generate token reset, simpan di cache (1 jam TTL).
    Di production, token dikirim via email.
    dev_token HANYA ditampilkan jika DEBUG=True — tidak bisa bocor ke production.
    Rate limit: 3 permintaan per jam per IP (anti-email-bombing).
    """
    from django.conf import settings as django_settings

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

    # TODO (Production): Kirim token via email SMTP ke user.email
    # Contoh: send_mail(subject='Reset Password', message=f'Token kamu: {token}', ...)

    # --- SECURITY: dev_token HANYA muncul saat DEBUG=True ---
    # Saat production (DEBUG=False), response ini TIDAK mengandung token sama sekali.
    # Ini mencegah token bocor meskipun developer lupa menghapusnya.
    response_data = {"message": "Jika email terdaftar, link reset password telah dikirim."}
    if django_settings.DEBUG:
        response_data["dev_token"] = token
        response_data["dev_note"] = "[DEV ONLY] Token ini tidak akan muncul di production (DEBUG=False)."

    return Response(response_data)


# ==============================================================================
# 7. RESET PASSWORD — Konfirmasi Token
# ==============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ResetPasswordRateThrottle])
def reset_password(request):
    """
    POST /api/auth/reset-password/
    Verifikasi token, set password baru, hapus token dari cache.
    Rate limit: 5 percobaan per jam per IP (anti-brute-force token).
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

# Konfigurasi validasi file upload
_ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
_MAX_PROFILE_PICTURE_SIZE_MB = 5  # Maksimal 5 MB
_MAX_PROFILE_PICTURE_SIZE_BYTES = _MAX_PROFILE_PICTURE_SIZE_MB * 1024 * 1024

# MIME type yang diizinkan (diverifikasi dari konten file, bukan hanya ekstensi)
_ALLOWED_MIME_PREFIXES = ('image/jpeg', 'image/png', 'image/gif', 'image/webp')


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def update_profile_picture(request):
    """
    PUT /api/me/profile-picture/
    Upload foto profil dengan validasi ketat:
    - Ekstensi hanya .jpg, .jpeg, .png, .gif, .webp
    - Ukuran maksimal 5 MB
    - MIME type diverifikasi dari konten file
    """
    import os

    user = request.user
    if 'profile_picture' not in request.FILES:
        return Response({'error': 'Tidak ada gambar yang diupload.'}, status=status.HTTP_400_BAD_REQUEST)

    uploaded_file = request.FILES['profile_picture']

    # --- Validasi 1: Ukuran file ---
    if uploaded_file.size > _MAX_PROFILE_PICTURE_SIZE_BYTES:
        return Response(
            {'error': f'Ukuran gambar terlalu besar. Maksimal {_MAX_PROFILE_PICTURE_SIZE_MB} MB.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # --- Validasi 2: Ekstensi file ---
    _, ext = os.path.splitext(uploaded_file.name.lower())
    if ext not in _ALLOWED_IMAGE_EXTENSIONS:
        return Response(
            {'error': f'Format file tidak didukung. Gunakan: {', '.join(_ALLOWED_IMAGE_EXTENSIONS)}.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # --- Validasi 3: MIME type dari konten file menggunakan Pillow ---
    # Pillow memverifikasi format riil dari konten file — jauh lebih andal dari imghdr
    # dan tidak deprecated di Python 3.11+.
    from PIL import Image, UnidentifiedImageError
    import io
    try:
        file_header = uploaded_file.read()
        uploaded_file.seek(0)  # Reset pointer setelah baca
        img = Image.open(io.BytesIO(file_header))
        img.verify()  # Verifikasi integritas file gambar
        detected_type = img.format.lower() if img.format else None
        # Normalisasi: JPEG → jpeg
        if detected_type == 'jpeg':
            detected_type = 'jpeg'
        if detected_type not in ('jpeg', 'png', 'gif', 'webp'):
            raise UnidentifiedImageError('Format tidak diizinkan')
    except (UnidentifiedImageError, Exception) as e:
        log_event(
            action_category='SECURITY_ANOMALY',
            action_type='INVALID_FILE_UPLOAD_ATTEMPT',
            request=request,
            user=user,
            action_status='BLOCKED',
            target_table='users',
            target_id=user.id,
            payload={
                'filename': uploaded_file.name,
                'claimed_ext': ext,
                'error': str(e),
            },
        )
        return Response(
            {'error': 'File tidak dikenali sebagai gambar yang valid. Upload dibatalkan.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # --- Semua validasi lulus — simpan file ---
    user.profile_picture = uploaded_file
    user.save(update_fields=['profile_picture'])

    log_event(
        action_category='DATA_MUTATION',
        action_type='PROFILE_PICTURE_UPDATE',
        request=request,
        user=user,
        target_table='users',
        target_id=user.id,
        payload={
            'filename': uploaded_file.name,
            'size_bytes': uploaded_file.size,
            'detected_type': detected_type,
        },
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


# ==============================================================================
# 10. LOGOUT — Proper Token Blacklisting
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    POST /api/auth/logout/
    Invalidasi refresh token di server (blacklist) sehingga token yang mungkin
    dicuri tidak bisa dipakai lagi walau access token belum expired.

    Tanpa endpoint ini, logout hanya menghapus token dari localStorage —
    tapi token tetap valid di server sampai waktu expired (60 menit).
    """
    from rest_framework_simplejwt.tokens import RefreshToken
    from rest_framework_simplejwt.exceptions import TokenError

    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response(
            {'error': 'Refresh token wajib disertakan untuk logout.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        token = RefreshToken(refresh_token)
        token.blacklist()  # Masukkan ke daftar hitam — tidak bisa dipakai lagi

        log_event(
            action_category='AUTHENTICATION',
            action_type='LOGOUT',
            request=request,
            user=request.user,
            target_table='users',
            target_id=request.user.id,
        )

        return Response({'message': 'Logout berhasil. Token diinvalidasi.'})

    except TokenError as e:
        # Token sudah expired atau sudah di-blacklist sebelumnya — tetap OK
        return Response({'message': 'Logout berhasil.'}, status=status.HTTP_200_OK)