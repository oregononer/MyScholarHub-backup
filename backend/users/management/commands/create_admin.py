"""
Management Command: Create / Replace Admin User
Sesuai spec: Admin TIDAK bisa register via UI publik, hanya via management command.

Penggunaan:
    # Buat admin baru
    python manage.py create_admin --username admin --email admin@scholarhub.com --password Admin123@

    # Ganti admin lama (hapus semua admin lama, buat yang baru)
    python manage.py create_admin --username admin --email admin@scholarhub.com --password Admin123@ --replace
"""
import re
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from users.models import CustomUser

logger = logging.getLogger('scholarhub')

# Regex: minimal 8 karakter, 1 huruf besar, 1 huruf kecil, 1 angka, 1 karakter spesial
_PASSWORD_REGEX = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]).{8,}$'
)


def _validate_password_strength(password: str) -> None:
    """Validasi kekuatan password secara lokal (sebelum Django validators)."""
    if not _PASSWORD_REGEX.match(password):
        raise CommandError(
            'Password tidak memenuhi syarat keamanan:\n'
            '  - Minimal 8 karakter\n'
            '  - Minimal 1 huruf besar (A-Z)\n'
            '  - Minimal 1 huruf kecil (a-z)\n'
            '  - Minimal 1 angka (0-9)\n'
            '  - Minimal 1 karakter spesial (!@#$%^&*...)'
        )


class Command(BaseCommand):
    help = 'Buat atau ganti akun Admin (satu-satunya cara membuat Admin sesuai spec keamanan)'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='Username admin baru')
        parser.add_argument('--email',    type=str, required=True, help='Email admin baru')
        parser.add_argument('--password', type=str, required=True, help='Password admin baru')
        parser.add_argument(
            '--replace',
            action='store_true',
            default=False,
            help='Hapus semua akun ADMIN yang ada sebelum membuat yang baru',
        )

    def handle(self, *args, **options):
        username = options['username'].strip()
        email    = options['email'].strip().lower()
        password = options['password']          # Jangan strip password
        replace  = options['replace']

        # ── 1. Validasi kekuatan password ─────────────────────────────────────
        _validate_password_strength(password)

        # ── 2. Validasi format email minimal ──────────────────────────────────
        if '@' not in email or '.' not in email.split('@')[-1]:
            raise CommandError(f'Email "{email}" tidak valid.')

        with transaction.atomic():
            # ── 3. Mode --replace: hapus semua admin lama ─────────────────────
            if replace:
                old_admins = CustomUser.objects.filter(role='ADMIN')
                count = old_admins.count()
                if count:
                    old_admins.delete()
                    self.stdout.write(
                        self.style.WARNING(f'[REPLACE] {count} akun admin lama dihapus.')
                    )
                    # Catat ke audit log tanpa menyebut password
                    logger.warning(
                        'ADMIN_REPLACE: %d akun admin lama dihapus oleh management command.',
                        count,
                    )
            else:
                # ── 4. Tanpa --replace: cek konflik ───────────────────────────
                if CustomUser.objects.filter(username=username).exists():
                    raise CommandError(
                        f'Username "{username}" sudah ada. '
                        'Gunakan --replace untuk menghapus admin lama terlebih dahulu.'
                    )
                if CustomUser.objects.filter(email=email).exists():
                    raise CommandError(
                        f'Email "{email}" sudah terdaftar. '
                        'Gunakan --replace untuk menghapus admin lama terlebih dahulu.'
                    )

            # ── 5. Buat admin baru ────────────────────────────────────────────
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,   # Django akan hash dengan Argon2 (sesuai settings)
                role='ADMIN',
                is_staff=True,
                is_superuser=True,
            )

        # Log sukses — TANPA password (secure coding)
        logger.info(
            'ADMIN_CREATED: username=%s email=%s id=%s',
            user.username, user.email, user.id,
        )

        self.stdout.write(self.style.SUCCESS(
            f'\nAdmin berhasil dibuat!\n'
            f'  Username : {user.username}\n'
            f'  Email    : {user.email}\n'
            f'  Role     : {user.role}\n'
            f'  ID       : {user.id}\n'
            f'  Password : [HIDDEN — tersimpan dalam hash Argon2]\n'
        ))
