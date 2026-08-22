from django.urls import path
from . import views

urlpatterns = [
    path('gigs/<int:gig_id>/review/', views.create_review, name='create_review'),
]
