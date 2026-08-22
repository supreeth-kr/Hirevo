from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('gigs/', views.gig_list, name='gig_list'),
    path('gigs/<int:pk>/', views.gig_detail, name='gig_detail'),
    path('gigs/create/', views.gig_create, name='gig_create'),
    path('gigs/my/', views.my_gigs, name='my_gigs'),
    path('gigs/<int:pk>/delete/', views.gig_delete, name='gig_delete'),
]
