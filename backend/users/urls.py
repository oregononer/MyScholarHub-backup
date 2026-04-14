from django.urls import path
from . import views

urlpatterns = [
    # --- Profil (Anti-IDOR: selalu data sendiri) ---
    path('me/profile/', views.get_my_profile, name='get_profile'),
    path('me/profile/update/', views.update_my_profile, name='update_profile'),
    path('me/profile/picture/', views.update_profile_picture, name='update_picture'),
    path('me/change-password/', views.change_password, name='change_password'),
    # --- Logout (Server-side token blacklist) ---
    path('auth/logout/', views.logout_view, name='logout'),
]