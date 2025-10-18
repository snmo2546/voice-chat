from django.urls import path, include
from rest_framework import routers

# API routes for chat functionality
router = routers.DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]