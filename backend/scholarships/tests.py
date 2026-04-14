"""
Unit Tests — Scholarships App
==============================
Cakupan test:
- Public catalog (tanpa login)  
- IDOR protection di submission_tracking
- Moderation actions (approve/reject) hanya admin
- Bookmark anti-duplikat

Catatan: RBACMiddleware membaca JWT dari header sehingga force_authenticate()
tidak cukup — perlu menonaktifkan middleware saat test atau inject JWT sungguhan.
Solusi yang dipilih: patch middleware menggunakan @override_settings untuk
mengeluarkan RBACMiddleware dari MIDDLEWARE saat test berjalan.
"""

from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from users.models import CustomUser
from scholarships.models import Category, Scholarship, Bookmark


# ──────────────────────────────────────────────────────────────────────────────
# Test Settings — tanpa RBACMiddleware agar force_authenticate bekerja
# ──────────────────────────────────────────────────────────────────────────────

TEST_MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # RBACMiddleware sengaja tidak disertakan — ditest secara terpisah
]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def make_user(username, role='APPLICANT', password='TestPass123!'):
    return CustomUser.objects.create_user(
        username=username,
        email=f'{username}@test.com',
        password=password,
        role=role,
    )


def make_scholarship(title='Test Beasiswa', status_val='PUBLISHED', created_by=None):
    cat, _ = Category.objects.get_or_create(name='Umum', defaults={'slug': 'umum'})
    return Scholarship.objects.create(
        title=title,
        provider_name='Provider Test',
        provider_email='provider@test.com',
        description='Deskripsi beasiswa test.',
        external_link='https://example.com',
        deadline='2030-12-31',
        status=status_val,
        category=cat,
        created_by=created_by,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 1. Public Catalog — Tidak perlu auth, tidak perlu middleware patch
# ──────────────────────────────────────────────────────────────────────────────

class PublicCatalogTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.scholarship = make_scholarship()

    def test_list_published_no_auth(self):
        """Guest bisa melihat katalog beasiswa published."""
        resp = self.client.get('/api/scholarships/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_does_not_expose_external_link_to_guest(self):
        """external_link TIDAK boleh muncul di public catalog untuk guest."""
        resp = self.client.get('/api/scholarships/')
        results = resp.data.get('results', resp.data)
        if results:
            self.assertNotIn('external_link', results[0])

    def test_pending_scholarship_not_in_public(self):
        """Beasiswa PENDING tidak boleh muncul di katalog publik."""
        make_scholarship(title='Pending BS', status_val='PENDING')
        resp = self.client.get('/api/scholarships/')
        results = resp.data.get('results', resp.data)
        titles = [r['title'] for r in results]
        self.assertNotIn('Pending BS', titles)

    def test_search_filter_returns_match(self):
        """Parameter ?q= memfilter beasiswa berdasarkan judul."""
        make_scholarship(title='Beasiswa ITB 2026')
        resp = self.client.get('/api/scholarships/?q=ITB')
        results = resp.data.get('results', resp.data)
        self.assertTrue(any('ITB' in r['title'] for r in results))

    def test_search_filter_excludes_non_match(self):
        """Parameter ?q= tidak menampilkan beasiswa yang tidak cocok."""
        make_scholarship(title='Beasiswa Harvard')
        resp = self.client.get('/api/scholarships/?q=ITB')
        results = resp.data.get('results', resp.data)
        titles = [r['title'] for r in results]
        self.assertNotIn('Beasiswa Harvard', titles)

    def test_public_stats_returns_counts(self):
        """/api/stats/ mengembalikan total_scholarships dan total_categories."""
        resp = self.client.get('/api/stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_scholarships', resp.data)
        self.assertIn('total_categories', resp.data)

    def test_public_stats_count_is_correct(self):
        """Jumlah beasiswa di stats sesuai dengan yang published."""
        resp1 = self.client.get('/api/stats/')
        count_before = resp1.data['total_scholarships']
        make_scholarship(title='Beasiswa Baru')
        resp2 = self.client.get('/api/stats/')
        self.assertEqual(resp2.data['total_scholarships'], count_before + 1)


# ──────────────────────────────────────────────────────────────────────────────
# 2. Submission Tracking — Anti-IDOR
# ──────────────────────────────────────────────────────────────────────────────

@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class SubmissionTrackingIDORTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner  = make_user('owner_user')
        self.other  = make_user('other_user')
        self.scholarship = make_scholarship(
            title='Private Submission',
            status_val='PENDING',
            created_by=self.owner,
        )
        self.url = f'/api/promotions/{self.scholarship.id}/status/'

    def test_owner_can_track(self):
        """Pemilik submission bisa melihat status tracking-nya."""
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_other_user_blocked_with_403(self):
        """User lain mendapat 403 saat coba akses tracking ID orang lain (Anti-IDOR)."""
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_blocked(self):
        """Guest tidak bisa akses tracking — wajib login."""
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ──────────────────────────────────────────────────────────────────────────────
# 3. Moderation — Admin Only (RBAC)
# ──────────────────────────────────────────────────────────────────────────────

@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class ModerationPermissionTest(TestCase):
    def setUp(self):
        self.client    = APIClient()
        self.admin     = make_user('admin_user',     role='ADMIN')
        self.applicant = make_user('applicant_user', role='APPLICANT')
        self.scholarship = make_scholarship(title='Pending Beasiswa', status_val='PENDING')
        self.approve_url = f'/api/admin/scholarships/{self.scholarship.id}/approve/'
        self.reject_url  = f'/api/admin/scholarships/{self.scholarship.id}/reject/'

    def test_admin_can_approve(self):
        """Admin bisa approve beasiswa PENDING → status jadi PUBLISHED."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.approve_url, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.scholarship.refresh_from_db()
        self.assertEqual(self.scholarship.status, 'PUBLISHED')

    def test_approve_response_has_email_sent_field(self):
        """Response approve menyertakan field email_sent."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.approve_url, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('email_sent', resp.data)

    def test_applicant_cannot_approve(self):
        """Applicant tidak bisa approve beasiswa (RBAC enforcement)."""
        self.client.force_authenticate(user=self.applicant)
        resp = self.client.post(self.approve_url, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_reject_with_reason(self):
        """Admin bisa reject beasiswa PENDING dengan alasan."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.reject_url,
            data={'rejection_reason': 'Link beasiswa tidak valid.'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.scholarship.refresh_from_db()
        self.assertEqual(self.scholarship.status, 'REJECTED')
        self.assertIn('Link beasiswa tidak valid', self.scholarship.rejection_reason)

    def test_cannot_approve_already_published(self):
        """Tidak bisa approve beasiswa yang sudah PUBLISHED — harus return 400."""
        published = make_scholarship(title='Sudah Publish', status_val='PUBLISHED')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            f'/api/admin/scholarships/{published.id}/approve/',
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_access_admin(self):
        """Guest tidak bisa akses admin endpoint."""
        self.client.force_authenticate(user=None)
        resp = self.client.post(self.approve_url, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ──────────────────────────────────────────────────────────────────────────────
# 4. Bookmark — Anti-Duplikat & Anti-IDOR
# ──────────────────────────────────────────────────────────────────────────────

@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class BookmarkTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user('bookmark_user')
        self.scholarship = make_scholarship()
        self.client.force_authenticate(user=self.user)

    def test_can_bookmark(self):
        """Applicant bisa bookmark beasiswa."""
        resp = self.client.post('/api/me/bookmarks/', {
            'scholarship': str(self.scholarship.id),
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_cannot_duplicate_bookmark(self):
        """Tidak bisa bookmark beasiswa yang sama dua kali → 400."""
        self.client.post('/api/me/bookmarks/', {
            'scholarship': str(self.scholarship.id),
        }, format='json')
        resp = self.client.post('/api/me/bookmarks/', {
            'scholarship': str(self.scholarship.id),
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_see_own_bookmarks(self):
        """User hanya melihat bookmark milik sendiri (Anti-IDOR)."""
        other = make_user('other_bookmark')
        other_scholarship = make_scholarship(title='Beasiswa Orang Lain')
        Bookmark.objects.create(user=other, scholarship=other_scholarship)

        resp = self.client.get('/api/me/bookmarks/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results', resp.data)
        ids = [str(b['scholarship']) for b in results]
        self.assertNotIn(str(other_scholarship.id), ids)

    def test_unauthenticated_cannot_bookmark(self):
        """Guest tidak bisa akses bookmark — wajib login."""
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/me/bookmarks/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
