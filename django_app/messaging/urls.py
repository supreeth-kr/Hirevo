from django.urls import path
from . import views

urlpatterns = [
    path('', views.conversations_list, name='conversations'),
    path('<int:pk>/', views.conversation_detail, name='conversation_detail'),
    path('start/<int:seller_id>/', views.start_conversation, name='start_conversation'),
]
