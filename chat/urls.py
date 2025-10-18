from django.urls import path, include
from rest_framework import routers
from . import views

# API routes for chat functionality
router = routers.DefaultRouter()

urlpatterns = [
    path('upload-recording/', views.UploadRecordingView.as_view(), name='upload_recording'),
    path('send-message/', views.SendMessageView.as_view(), name='send_message'),
    path('', include(router.urls)),
]