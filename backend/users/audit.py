"""
Utility untuk mencatat Audit Log secara konsisten.
Dipanggil dari views, middleware, dan signals.
"""
import logging
from .models import AuditLog

logger = logging.getLogger('scholarhub')


def log_event(
    action_category,
    action_type,
    request=None,
    user=None,
    target_table='',
    target_id='',
    action_status='SUCCESS',
    payload=None,
):
    """
    Catat event ke tabel audit_logs.

    Args:
        action_category: AUTHENTICATION | AUTHORIZATION | DATA_MUTATION | SYSTEM | SECURITY_ANOMALY
        action_type: e.g. LOGIN_SUCCESS, SCHOLARSHIP_APPROVED, RATE_LIMIT_EXCEEDED
        request: Django request object (untuk IP dan User-Agent)
        user: CustomUser instance atau None (untuk Guest)
        target_table: nama tabel yang terpengaruh
        target_id: ID record yang terpengaruh
        action_status: SUCCESS | FAILED | BLOCKED
        payload: dict tambahan (akan disimpan sebagai JSON)
    """
    ip_address = None
    user_agent = ''

    if request:
        ip_address = _get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        if user is None and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user

    try:
        AuditLog.objects.create(
            user=user,
            action_category=action_category,
            action_type=action_type,
            target_table=target_table,
            target_id=str(target_id) if target_id else '',
            action_status=action_status,
            payload=payload,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception as e:
        # Audit log failure TIDAK boleh crash aplikasi
        logger.error(f"AUDIT LOG WRITE FAILED: {action_category}/{action_type} — {e}")


def _get_client_ip(request):
    """Ambil IP client, support proxy (X-Forwarded-For)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
