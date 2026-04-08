"""
Management Command: Create Admin User
Sesuai spec: Admin TIDAK bisa register via UI publik, hanya via management command.

Penggunaan:
    python manage.py create_admin --username admin --email admin@scholarhub.com --password SecureP@ss123
"""
from django.core.management.base import BaseCommand
from users.models import CustomUser


class Command(BaseCommand):
    help = 'Buat akun Admin baru (satu-satunya cara membuat Admin sesuai spec keamanan)'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='Username admin')
        parser.add_argument('--email', type=str, required=True, help='Email admin')
        parser.add_argument('--password', type=str, required=True, help='Password admin')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        if CustomUser.objects.filter(username=username).exists():
            self.stderr.write(self.style.ERROR(f'Username "{username}" sudah ada!'))
            return

        if CustomUser.objects.filter(email=email).exists():
            self.stderr.write(self.style.ERROR(f'Email "{email}" sudah terdaftar!'))
            return

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            role='ADMIN',
            is_staff=True,
            is_superuser=True,
        )

        self.stdout.write(self.style.SUCCESS(
            f'Admin berhasil dibuat!\n'
            f'  Username : {user.username}\n'
            f'  Email    : {user.email}\n'
            f'  Role     : {user.role}\n'
            f'  ID       : {user.id}'
        ))
