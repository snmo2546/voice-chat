from django.urls import path, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()

urlpatterns = [
    path('', views.chat_interface, name='chat_interface'),
    path('api/', include(router.urls)),
]
