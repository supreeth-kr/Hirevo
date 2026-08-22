from django.urls import path
from . import views

urlpatterns = [
    path('', views.recommendations_api, name='recommendations_api'),
]
