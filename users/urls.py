from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('setup/', views.setup_view, name='setup'),
    path('profile/', views.profile_view, name='profile'),
    path('keys/', views.user_keys_view, name='keys'),
    path('ping/', views.ping_view, name='ping'),
    path('check-setup/', views.check_setup_status, name='check_setup'),
]