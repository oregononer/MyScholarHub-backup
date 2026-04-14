"""
Scholarship Email Notifications
================================
Mengirim notifikasi email ke provider beasiswa saat status berubah.

Dev Mode  : Email dicetak ke terminal (console backend) — tidak perlu SMTP.
Production: Email dikirim via SMTP — konfigurasi dari environment variables.

Semua fungsi di sini fail-safe: jika email gagal dikirim, error dicatat ke
audit log dan proses moderasi TETAP berhasil (tidak di-rollback).
"""

import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger('scholarhub')


def _build_approve_body(scholarship) -> tuple[str, str]:
    """Kembalikan (subject, body) untuk notifikasi approve."""
    subject = f"Beasiswa Anda Telah Disetujui: {scholarship.title}"
    body = f"""Halo {scholarship.provider_name},

Kami dengan senang hati menginformasikan bahwa beasiswa yang Anda ajukan
telah DISETUJUI dan dipublikasikan di platform myscholarhub.

Detail Beasiswa:
  Judul    : {scholarship.title}
  Deadline : {scholarship.deadline}
  Tracking : {scholarship.id}

Beasiswa Anda kini dapat dilihat oleh ribuan calon pelajar di platform kami.

Terima kasih telah mempercayai myscholarhub sebagai mitra program beasiswa Anda.

Salam,
Tim myscholarhub
--
Email: myscholarhub@gmail.com
Website: http://myscholarhub.id
"""
    return subject, body


def _build_reject_body(scholarship) -> tuple[str, str]:
    """Kembalikan (subject, body) untuk notifikasi reject."""
    subject = f"Update Pengajuan Beasiswa: {scholarship.title}"
    body = f"""Halo {scholarship.provider_name},

Kami telah meninjau pengajuan beasiswa Anda dan dengan menyesal menginformasikan
bahwa pengajuan tersebut TIDAK DAPAT DISETUJUI saat ini.

Detail Pengajuan:
  Judul    : {scholarship.title}
  Tracking : {scholarship.id}

Alasan Penolakan:
  {scholarship.rejection_reason or 'Tidak ada alasan spesifik yang diberikan.'}

Anda dapat mengajukan kembali setelah memperbaiki kekurangan yang disebutkan.
Jika Anda memiliki pertanyaan, silakan hubungi tim kami.

Salam,
Tim myscholarhub
--
Email: myscholarhub@gmail.com
Website: http://myscholarhub.id
"""
    return subject, body


def send_approval_notification(scholarship, audit_callback=None) -> bool:
    """
    Kirim email notifikasi APPROVE ke provider_email.

    Returns:
        True  — email berhasil dikirim (atau dicetak ke console di dev mode)
        False — email gagal, error sudah di-log

    Fail-safe: jika email gagal, proses approve TIDAK di-rollback.
    """
    if not scholarship.provider_email:
        logger.warning(
            f"[EMAIL] Tidak ada provider_email untuk scholarship {scholarship.id} — skip."
        )
        return False

    subject, body = _build_approve_body(scholarship)

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[scholarship.provider_email],
            fail_silently=False,
        )
        logger.info(
            f"[EMAIL] Approve notification sent → {scholarship.provider_email} "
            f"(scholarship: {scholarship.id})"
        )
        return True

    except Exception as e:
        logger.error(
            f"[EMAIL] Gagal mengirim approve notification ke {scholarship.provider_email}: {e}"
        )
        # Panggil audit callback jika ada (untuk catat EMAIL_FAILED ke audit log)
        if audit_callback:
            audit_callback(error=str(e))
        return False


def send_rejection_notification(scholarship, audit_callback=None) -> bool:
    """
    Kirim email notifikasi REJECT ke provider_email.

    Returns:
        True  — email berhasil dikirim
        False — email gagal, error sudah di-log

    Fail-safe: jika email gagal, proses reject TIDAK di-rollback.
    """
    if not scholarship.provider_email:
        logger.warning(
            f"[EMAIL] Tidak ada provider_email untuk scholarship {scholarship.id} — skip."
        )
        return False

    subject, body = _build_reject_body(scholarship)

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[scholarship.provider_email],
            fail_silently=False,
        )
        logger.info(
            f"[EMAIL] Reject notification sent → {scholarship.provider_email} "
            f"(scholarship: {scholarship.id})"
        )
        return True

    except Exception as e:
        logger.error(
            f"[EMAIL] Gagal mengirim reject notification ke {scholarship.provider_email}: {e}"
        )
        if audit_callback:
            audit_callback(error=str(e))
        return False
