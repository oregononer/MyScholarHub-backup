"""
Scholarship Views — Public Zone, Applicant Zone, Admin Zone.
Setiap zone memiliki permission dan serializer berbeda.
"""
import requests
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets, permissions, generics
from rest_framework.decorators import api_view, permission_classes, throttle_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .models import Category, Scholarship, Bookmark
from .serializers import (
    CategorySerializer,
    PublicScholarshipSerializer,
    DetailScholarshipSerializer,
    ScholarshipCreateSerializer,
    ProviderSubmissionSerializer,
    SubmissionTrackingSerializer,
    BookmarkSerializer,
    AdminScholarshipSerializer,
    ModerationActionSerializer,
)
from users.audit import log_event


# ==============================================================================
# CUSTOM PERMISSIONS
# ==============================================================================

class IsAdminRole(permissions.BasePermission):
    """Hanya user dengan role ADMIN."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'ADMIN'
        )


class IsAdminOrReadOnly(permissions.BasePermission):
    """Admin bisa CRUD, lainnya hanya bisa Read (GET)."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'ADMIN'
        )


# ==============================================================================
# CUSTOM THROTTLES
# ==============================================================================

class SubmissionThrottle(AnonRateThrottle):
    rate = '5/hour'


class TrackingThrottle(AnonRateThrottle):
    rate = '10/minute'


# ==============================================================================
# 1. PUBLIC ZONE — Katalog & Stats (Tanpa Login)
# ==============================================================================

class PublicScholarshipListView(generics.ListAPIView):
    """
    GET /api/scholarships/
    Katalog beasiswa untuk publik — TIDAK menyertakan external_link.
    Filter: category, education_level, coverage_type, q (search)
    """
    serializer_class = PublicScholarshipSerializer
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        """Dual serializer: Public untuk Guest, Detail untuk Applicant."""
        if self.request.user and self.request.user.is_authenticated:
            return DetailScholarshipSerializer
        return PublicScholarshipSerializer

    def get_queryset(self):
        qs = Scholarship.objects.filter(status='PUBLISHED').select_related('category')

        # Filters
        category = self.request.query_params.get('category')
        education = self.request.query_params.get('education_level')
        coverage = self.request.query_params.get('coverage_type')
        search = self.request.query_params.get('q')

        if category:
            qs = qs.filter(category__slug=category)
        if education:
            qs = qs.filter(education_level=education)
        if coverage:
            qs = qs.filter(coverage_type=coverage)
        if search:
            qs = qs.filter(title__icontains=search)

        return qs.order_by('deadline')


class PublicScholarshipDetailView(generics.RetrieveAPIView):
    """
    GET /api/scholarships/{slug}/
    Detail beasiswa — Guest lihat PublicSerializer, Applicant lihat DetailSerializer.
    """
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.request.user and self.request.user.is_authenticated:
            return DetailScholarshipSerializer
        return PublicScholarshipSerializer

    def get_queryset(self):
        return Scholarship.objects.filter(status='PUBLISHED').select_related('category')


@api_view(['GET'])
@permission_classes([AllowAny])
def public_stats(request):
    """
    GET /api/stats/ — Statistik publik untuk landing page.
    """
    return Response({
        'total_scholarships': Scholarship.objects.filter(status='PUBLISHED').count(),
        'total_categories': Category.objects.filter(is_active=True).count(),
    })


class PublicCategoryListView(generics.ListAPIView):
    """GET /api/categories/ — Daftar kategori aktif (publik)."""
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    queryset = Category.objects.filter(is_active=True)
    pagination_class = None  # Kategori biasanya sedikit, tidak perlu pagination


# ==============================================================================
# 2. PROVIDER SUBMISSION — Form Pengajuan (Wajib Login)
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([SubmissionThrottle])
def provider_submission(request):
    """
    POST /api/submissions/ — User mengajukan beasiswa baru.
    Status otomatis PENDING. Wajib login. Rate limit: 5 req/jam.
    """
    serializer = ProviderSubmissionSerializer(data=request.data)
    if serializer.is_valid():
        scholarship = serializer.save(status='PENDING', created_by=request.user)

        log_event(
            action_category='DATA_MUTATION',
            action_type='SUBMISSION_CREATED',
            request=request,
            user=request.user,
            target_table='scholarships',
            target_id=scholarship.id,
            payload={
                'title': scholarship.title,
                'provider_email': scholarship.provider_email,
                'tracking_id': str(scholarship.id),
            },
        )

        return Response({
            'message': 'Pengajuan berhasil diterima! Simpan Tracking ID untuk memantau status.',
            'tracking_id': str(scholarship.id),
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([TrackingThrottle])
def submission_tracking(request, tracking_id):
    """
    GET /api/submissions/{uuid}/status/ — Cek status pengajuan.
    Wajib login. Rate limit: 10 req/menit.
    """
    scholarship = get_object_or_404(Scholarship, id=tracking_id)
    serializer = SubmissionTrackingSerializer(scholarship)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_submissions(request):
    """
    GET /api/me/submissions/ — Daftar semua pengajuan user yang sedang login.
    Anti-IDOR: hanya menampilkan submission milik user sendiri.
    """
    scholarships = Scholarship.objects.filter(
        created_by=request.user
    ).select_related('category').order_by('-created_at')

    data = [{
        'id': str(s.id),
        'title': s.title,
        'provider_name': s.provider_name,
        'status': s.status,
        'rejection_reason': s.rejection_reason,
        'created_at': s.created_at.isoformat(),
        'deadline': str(s.deadline),
        'category_name': s.category.name if s.category else None,
    } for s in scholarships]

    return Response(data)


# ==============================================================================
# 3. APPLICANT ZONE — Bookmark & Recommendations
# ==============================================================================

class BookmarkViewSet(viewsets.ModelViewSet):
    """
    /api/me/bookmarks/ — CRUD bookmark.
    Anti-IDOR: queryset selalu filter by request.user.
    """
    serializer_class = BookmarkSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete']  # Tidak ada PUT/PATCH

    def get_queryset(self):
        # Anti-IDOR: Hanya tampilkan bookmark milik user yang login
        return Bookmark.objects.filter(
            user=self.request.user
        ).select_related('scholarship')

    def create(self, request, *args, **kwargs):
        scholarship_id = request.data.get('scholarship')

        # Cek duplikat
        if Bookmark.objects.filter(user=request.user, scholarship_id=scholarship_id).exists():
            return Response(
                {"detail": "Beasiswa ini sudah ada di daftar simpanan kamu!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)

        log_event(
            action_category='DATA_MUTATION',
            action_type='BOOKMARK_ADD',
            request=request,
            target_table='user_bookmarks',
            target_id=scholarship_id,
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        scholarship_id = instance.scholarship_id

        log_event(
            action_category='DATA_MUTATION',
            action_type='BOOKMARK_REMOVE',
            request=request,
            target_table='user_bookmarks',
            target_id=scholarship_id,
        )

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recommendations(request):
    """
    GET /api/me/recommendations/ — Rekomendasi berdasarkan profil Applicant.
    Filter by education_level dan major dari ApplicantProfile.
    """
    user = request.user
    qs = Scholarship.objects.filter(status='PUBLISHED').select_related('category')

    # Coba match berdasarkan profil
    try:
        profile = user.applicant_profile
        if profile.education_level:
            qs = qs.filter(education_level=profile.education_level)
    except Exception:
        pass

    # Ambil 10 rekomendasi, urut deadline terdekat
    qs = qs.order_by('deadline')[:10]

    serializer = DetailScholarshipSerializer(qs, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_redirect_url(request, scholarship_id):
    """
    GET /api/scholarships/{id}/redirect-url/ — Outbound Gateway.
    Validasi URL via HTTP HEAD sebelum redirect.
    Catat OUTBOUND_CLICK ke audit log.
    """
    scholarship = get_object_or_404(Scholarship, id=scholarship_id, status='PUBLISHED')

    url = scholarship.external_link
    url_valid = False
    error_msg = None

    try:
        # Validasi URL saat diklik (bukan saat render) — sesuai spec
        head_response = requests.head(url, timeout=5, allow_redirects=True)
        url_valid = head_response.status_code < 400
    except requests.RequestException as e:
        error_msg = str(e)

    if url_valid:
        log_event(
            action_category='DATA_MUTATION',
            action_type='OUTBOUND_CLICK',
            request=request,
            target_table='scholarships',
            target_id=scholarship_id,
            payload={
                'url': url,
                'provider': scholarship.provider_name,
            },
        )
        return Response({
            'url': url,
            'provider_name': scholarship.provider_name,
            'valid': True,
        })
    else:
        log_event(
            action_category='SECURITY_ANOMALY',
            action_type='INVALID_REDIRECT_URL',
            request=request,
            action_status='BLOCKED',
            target_table='scholarships',
            target_id=scholarship_id,
            payload={'url': url, 'error': error_msg},
        )
        return Response({
            'valid': False,
            'error': 'URL tujuan tidak dapat dijangkau atau tidak valid. Redirect dibatalkan.',
        }, status=status.HTTP_502_BAD_GATEWAY)


# ==============================================================================
# 4. ADMIN ZONE — Moderation, CRUD, User Management
# ==============================================================================

class AdminScholarshipViewSet(viewsets.ModelViewSet):
    """
    /api/admin/scholarships/ — Full CRUD untuk Admin.
    Endpoint tambahan: approve, reject, takedown.
    """
    serializer_class = AdminScholarshipSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = Scholarship.objects.all().select_related('category', 'created_by', 'published_by')

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status='PUBLISHED')

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """POST /api/admin/scholarships/{id}/approve/"""
        scholarship = self.get_object()

        if scholarship.status != 'PENDING':
            return Response(
                {'error': f'Hanya beasiswa PENDING yang bisa di-approve. Status saat ini: {scholarship.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Link Integrity Check
        link_check = self._check_link(scholarship.external_link)

        scholarship.status = 'PUBLISHED'
        scholarship.published_by = request.user
        scholarship.save()

        log_event(
            action_category='DATA_MUTATION',
            action_type='SCHOLARSHIP_APPROVED',
            request=request,
            target_table='scholarships',
            target_id=scholarship.id,
            payload={
                'from_status': 'PENDING',
                'to_status': 'PUBLISHED',
                'link_check_result': link_check,
                'approved_by': str(request.user.id),
            },
        )

        return Response({
            'message': f'Beasiswa "{scholarship.title}" berhasil di-approve!',
            'link_check': link_check,
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """POST /api/admin/scholarships/{id}/reject/"""
        scholarship = self.get_object()

        if scholarship.status != 'PENDING':
            return Response(
                {'error': f'Hanya beasiswa PENDING yang bisa di-reject. Status saat ini: {scholarship.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ModerationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        scholarship.status = 'REJECTED'
        scholarship.rejection_reason = serializer.validated_data['rejection_reason']
        scholarship.save()

        log_event(
            action_category='DATA_MUTATION',
            action_type='SCHOLARSHIP_REJECTED',
            request=request,
            target_table='scholarships',
            target_id=scholarship.id,
            payload={
                'from_status': 'PENDING',
                'to_status': 'REJECTED',
                'rejection_reason': scholarship.rejection_reason,
            },
        )

        # TODO: Kirim email ke provider_email (implementasi SMTP saat production)

        return Response({
            'message': f'Beasiswa "{scholarship.title}" ditolak.',
            'rejection_reason': scholarship.rejection_reason,
        })

    @action(detail=True, methods=['post'])
    def takedown(self, request, pk=None):
        """POST /api/admin/scholarships/{id}/takedown/ — Soft delete ke DRAFT."""
        scholarship = self.get_object()
        old_status = scholarship.status

        scholarship.status = 'DRAFT'
        scholarship.save()

        log_event(
            action_category='DATA_MUTATION',
            action_type='SCHOLARSHIP_TAKEDOWN',
            request=request,
            target_table='scholarships',
            target_id=scholarship.id,
            payload={
                'from_status': old_status,
                'to_status': 'DRAFT',
            },
        )

        return Response({
            'message': f'Beasiswa "{scholarship.title}" berhasil di-takedown (soft-delete ke DRAFT).',
        })

    def _check_link(self, url):
        """Link Integrity Check — HTTP HEAD request ke external_link."""
        try:
            resp = requests.head(url, timeout=5, allow_redirects=True)
            return f"OK — {resp.status_code}"
        except requests.RequestException as e:
            return f"FAILED — {str(e)}"


class AdminCategoryViewSet(viewsets.ModelViewSet):
    """
    /api/admin/categories/ — CRUD kategori untuk Admin.
    Slug auto-generated dari name.
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAdminRole]
    queryset = Category.objects.all()


@api_view(['GET'])
@permission_classes([IsAdminRole])
def admin_stats(request):
    """GET /api/admin/stats/ — Dashboard stats untuk Admin."""
    from users.models import CustomUser, AuditLog

    return Response({
        'total_scholarships': Scholarship.objects.count(),
        'total_published': Scholarship.objects.filter(status='PUBLISHED').count(),
        'total_pending': Scholarship.objects.filter(status='PENDING').count(),
        'total_rejected': Scholarship.objects.filter(status='REJECTED').count(),
        'total_applicants': CustomUser.objects.filter(role='APPLICANT').count(),
        'total_admins': CustomUser.objects.filter(role='ADMIN').count(),
        'total_categories': Category.objects.filter(is_active=True).count(),
        'recent_anomalies': AuditLog.objects.filter(
            action_category='SECURITY_ANOMALY'
        ).count(),
    })


@api_view(['GET'])
@permission_classes([IsAdminRole])
def admin_audit_logs(request):
    """
    GET /api/admin/audit-logs/ — Audit trail viewer (READ-ONLY).
    Filter: action_category, action_status, user_id, limit
    """
    from users.models import AuditLog

    qs = AuditLog.objects.all().select_related('user').order_by('-created_at')

    # Filters
    category = request.query_params.get('action_category')
    action_status = request.query_params.get('action_status')
    user_id = request.query_params.get('user_id')
    limit = int(request.query_params.get('limit', 50))

    if category:
        qs = qs.filter(action_category=category)
    if action_status:
        qs = qs.filter(action_status=action_status)
    if user_id:
        qs = qs.filter(user_id=user_id)

    qs = qs[:limit]

    data = [{
        'id': str(log.id),
        'user': log.user.username if log.user else None,
        'action_category': log.action_category,
        'action_type': log.action_type,
        'action_status': log.action_status,
        'target_table': log.target_table,
        'target_id': log.target_id,
        'ip_address': log.ip_address,
        'user_agent': log.user_agent,
        'payload': log.payload,
        'created_at': log.created_at.isoformat(),
    } for log in qs]

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAdminRole])
def admin_users_list(request):
    """GET /api/admin/users/ — Daftar user untuk Admin."""
    from users.models import CustomUser

    role_filter = request.query_params.get('role')
    qs = CustomUser.objects.all().order_by('-date_joined')

    if role_filter:
        qs = qs.filter(role=role_filter)

    data = [{
        'id': str(u.id),
        'username': u.username,
        'email': u.email,
        'role': u.role,
        'is_active': u.is_active,
        'date_joined': u.date_joined.isoformat(),
        'last_login': u.last_login.isoformat() if u.last_login else None,
    } for u in qs]

    return Response(data)


@api_view(['POST'])
@permission_classes([IsAdminRole])
def admin_deactivate_user(request, user_id):
    """
    POST /api/admin/users/{id}/deactivate/
    Set is_active=False. Di production: invalidasi JWT via Redis blacklist.
    """
    from users.models import CustomUser

    user = get_object_or_404(CustomUser, id=user_id)

    if user.role == 'ADMIN':
        return Response(
            {'error': 'Tidak bisa menonaktifkan admin lain.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user.is_active = False
    user.save()

    log_event(
        action_category='DATA_MUTATION',
        action_type='ACCOUNT_DEACTIVATED',
        request=request,
        target_table='users',
        target_id=user.id,
        payload={'deactivated_user': user.username},
    )

    # TODO: Saat production, invalidasi JWT via Redis blacklist

    return Response({'message': f'User "{user.username}" berhasil dinonaktifkan.'})