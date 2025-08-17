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

    # Project management endpoints (new)
    path('projects/', views.project_list_create, name='project_list_create'),
    path('projects/<uuid:project_id>/', views.project_detail, name='project_detail'),
    path('projects/<uuid:project_id>/change-status/', views.project_change_status, name='project_change_status'),
    path('projects/stats/', views.project_stats, name='project_stats'),
    path('projects/search/', views.project_search, name='project_search'),
    
    # Client-Project relationship endpoints
    path('clients/<uuid:client_id>/projects/', views.projects_by_client, name='projects_by_client'),
]