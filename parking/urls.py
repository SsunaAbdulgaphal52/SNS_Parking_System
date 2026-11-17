from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # login and logout
    path('', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # parking a car, checking it out, paying and the receipt
    path('park/', views.park_car, name='park_car'),
    path('park/<int:lot_id>/', views.park_lot, name='park_lot'),
    path('tickets/<int:pk>/checkout/', views.checkout, name='checkout'),
    path('pay/', views.make_payment, name='make_payment'),
    path('payments/<int:pk>/receipt/', views.receipt, name='receipt'),

    # staff (managers only)
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.staff_add, name='staff_add'),
    path('staff/<int:pk>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<int:pk>/delete/', views.staff_delete, name='staff_delete'),

    # parking spots (list only)
    path('spots/', views.spot_list, name='spot_list'),

    # car owners
    path('owners/', views.owner_list, name='owner_list'),
    path('owners/add/', views.owner_add, name='owner_add'),
    path('owners/<int:pk>/edit/', views.owner_edit, name='owner_edit'),
    path('owners/<int:pk>/delete/', views.owner_delete, name='owner_delete'),

    # cars
    path('cars/', views.car_list, name='car_list'),
    path('cars/add/', views.car_add, name='car_add'),
    path('cars/<int:pk>/edit/', views.car_edit, name='car_edit'),
    path('cars/<int:pk>/delete/', views.car_delete, name='car_delete'),

    # parking lots
    path('lots/', views.lot_list, name='lot_list'),
    path('lots/add/', views.lot_add, name='lot_add'),
    path('lots/<int:pk>/edit/', views.lot_edit, name='lot_edit'),
    path('lots/<int:pk>/delete/', views.lot_delete, name='lot_delete'),

    # tickets
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/add/', views.ticket_add, name='ticket_add'),
    path('tickets/<int:pk>/edit/', views.ticket_edit, name='ticket_edit'),
    path('tickets/<int:pk>/delete/', views.ticket_delete, name='ticket_delete'),

    # payments (list, edit, delete)
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/<int:pk>/edit/', views.payment_edit, name='payment_edit'),
    path('payments/<int:pk>/delete/', views.payment_delete, name='payment_delete'),
]
