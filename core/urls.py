from django.urls import path
from core import views

urlpatterns = [
    # Temporary seeder - remove after use
    path('_seed/system-data/', views.seed_system_data, name='seed_system_data'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),

    # Flight Requests
    path('flights/', views.flights_list, name='flights_list'),
    path('flights/new/', views.flight_new, name='flight_new'),
    path('flights/create/', views.flight_create, name='flight_create'),
    path('flights/<int:pk>/edit/', views.flight_edit, name='flight_edit'),
    path('flights/<int:pk>/update/', views.flight_update, name='flight_update'),
    path('flights/<int:pk>/delete/', views.flight_delete, name='flight_delete'),
    path('flights/<int:pk>/approve/', views.flight_approve, name='flight_approve'),
    path('flights/<int:pk>/reject/', views.flight_reject, name='flight_reject'),

    # Daily Schedule
    path('schedule/', views.schedule_view, name='schedule'),
    path('schedule/allocate/', views.schedule_allocate, name='schedule_allocate'),
    path('schedule/clear/', views.schedule_clear, name='schedule_clear'),
    path('schedule/<int:flight_id>/allocate-manual/', views.schedule_allocate_manual, name='schedule_allocate_manual'),
    path('schedule/<int:flight_id>/allocate-manual-submit/', views.schedule_allocate_manual_submit, name='schedule_allocate_manual_submit'),
    
    # Season Resource Allocation
    path('allocations/', views.season_allocations_view, name='season_allocations'),
    path('allocations/assign/', views.season_allocations_assign, name='season_allocations_assign'),
    path('allocations/auto/', views.season_allocations_auto, name='season_allocations_auto'),
    path('allocations/recommendations/', views.auto_recommendations, name='auto_recommendations'),
    path('allocations/flight/<int:flight_id>/', views.flight_allocate_season, name='flight_allocate_season'),
    path('allocations/flight/<int:flight_id>/submit/', views.flight_allocate_season_submit, name='flight_allocate_season_submit'),
    path('allocations/flight/<int:flight_id>/resolve/', views.flight_resolve_conflict, name='flight_resolve_conflict'),
    path('allocations/flight/<int:flight_id>/resolve/apply/', views.flight_apply_resolution, name='flight_apply_resolution'),

    # Resources
    path('resources/', views.resources_view, name='resources'),

    # Reports
    path('reports/', views.reports_dashboard, name='reports'),
    path('reports/daily-analysis/', views.daily_analysis, name='daily_analysis'),
    path('reports/export/excel/', views.reports_export_excel, name='reports_export_excel'),
    path('reports/export/pdf/', views.reports_export_pdf, name='reports_export_pdf'),

    # Airlines Management
    path('manage/airlines/', views.airlines_list, name='airlines_list'),
    path('manage/airlines/new/', views.airline_new, name='airline_new'),
    path('manage/airlines/create/', views.airline_create, name='airline_create'),
    path('manage/airlines/<int:pk>/edit/', views.airline_edit, name='airline_edit'),
    path('manage/airlines/<int:pk>/update/', views.airline_update, name='airline_update'),
    path('manage/airlines/<int:pk>/delete/', views.airline_delete, name='airline_delete'),

    # Airports Management
    path('manage/airports/', views.airports_list, name='airports_list'),
    path('manage/airports/new/', views.airport_new, name='airport_new'),
    path('manage/airports/create/', views.airport_create, name='airport_create'),
    path('manage/airports/<int:pk>/edit/', views.airport_edit, name='airport_edit'),
    path('manage/airports/<int:pk>/update/', views.airport_update, name='airport_update'),
    path('manage/airports/<int:pk>/delete/', views.airport_delete, name='airport_delete'),

    # Aircraft Types Management
    path('manage/aircraft-types/', views.aircraft_types_list, name='aircraft_types_list'),
    path('manage/aircraft-types/new/', views.aircraft_type_new, name='aircraft_type_new'),
    path('manage/aircraft-types/create/', views.aircraft_type_create, name='aircraft_type_create'),
    path('manage/aircraft-types/<int:pk>/edit/', views.aircraft_type_edit, name='aircraft_type_edit'),
    path('manage/aircraft-types/<int:pk>/update/', views.aircraft_type_update, name='aircraft_type_update'),
    path('manage/aircraft-types/<int:pk>/delete/', views.aircraft_type_delete, name='aircraft_type_delete'),
]
