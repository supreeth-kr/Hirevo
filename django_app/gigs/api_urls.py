from django.urls import path
from . import api_views

urlpatterns = [
    path('gigs/', api_views.GigListAPI.as_view(), name='api_gigs'),
    path('gigs/<int:pk>/', api_views.GigDetailAPI.as_view(), name='api_gig_detail'),
]
