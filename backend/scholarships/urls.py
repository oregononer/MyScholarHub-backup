from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Admin routers
admin_router = DefaultRouter()
admin_router.register(r'scholarships', views.AdminScholarshipViewSet, basename='admin-scholarship')
admin_router.register(r'categories', views.AdminCategoryViewSet, basename='admin-category')

urlpatterns = [
    # === PUBLIC ZONE ===
    path('scholarships/', views.PublicScholarshipListView.as_view(), name='scholarship-list'),
    path('scholarships/<slug:slug>/', views.PublicScholarshipDetailView.as_view(), name='scholarship-detail'),
    path('categories/', views.PublicCategoryListView.as_view(), name='category-list'),
    path('stats/', views.public_stats, name='public-stats'),

    # === PROVIDER PROMOTION ===
    path('promotions/', views.provider_submission, name='provider-promotion'),
    path('promotions/<uuid:tracking_id>/status/', views.submission_tracking, name='promotion-tracking'),
    path('me/promotions/', views.my_submissions, name='my-promotions'),

    # === APPLICANT ZONE ===
    path('me/bookmarks/', views.BookmarkViewSet.as_view({
        'get': 'list',
        'post': 'create',
    }), name='bookmark-list'),
    path('me/bookmarks/<int:pk>/', views.BookmarkViewSet.as_view({
        'delete': 'destroy',
    }), name='bookmark-detail'),
    path('me/recommendations/', views.recommendations, name='recommendations'),
    path('scholarships/<uuid:scholarship_id>/redirect-url/', views.get_redirect_url, name='redirect-url'),

    # === ADMIN ZONE ===
    path('admin/', include(admin_router.urls)),
    path('admin/stats/', views.admin_stats, name='admin-stats'),
    path('admin/audit-logs/', views.admin_audit_logs, name='admin-audit-logs'),
    path('admin/users/', views.admin_users_list, name='admin-users-list'),
    path('admin/users/<uuid:user_id>/deactivate/', views.admin_deactivate_user, name='admin-deactivate-user'),
]
