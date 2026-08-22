from django.urls import path
from . import views

urlpatterns = [
    path('', views.orders_list, name='orders'),
    path('pay/<int:gig_id>/', views.pay, name='pay'),
    path('pay/<int:gig_id>/intent/', views.create_payment_intent, name='payment_intent'),
    path('success/', views.payment_success, name='payment_success'),
]
