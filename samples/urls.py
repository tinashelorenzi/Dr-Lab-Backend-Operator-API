# samples/urls.py
from django.urls import path
from . import views

app_name = 'samples'

urlpatterns = [
    # Client management endpoints
    path('clients/', views.client_list_create, name='client_list_create'),
    path('clients/<uuid:client_id>/', views.client_detail, name='client_detail'),
    path('clients/<uuid:client_id>/toggle-status/', views.client_toggle_status, name='client_toggle_status'),
    path('clients/stats/', views.client_stats, name='client_stats'),
    path('clients/search/', views.client_search, name='client_search'),
]