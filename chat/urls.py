from django.urls import path, include
from rest_framework import routers
from . import views

# API routes for chat functionality
router = routers.DefaultRouter()

urlpatterns = [
    path('upload-recording/', views.UploadRecordingView.as_view(), name='upload_recording'),
    path('send-message/', views.SendMessageView.as_view(), name='send_message'),
    path('voice-profiles/', views.VoiceProfileListView.as_view(), name='voice_profile_list'),
    path('voice-profiles/<str:voice_id>/', views.VoiceProfileUpdateView.as_view(), name='voice_profile_update'),
    path('upload-voice-profile/', views.VoiceProfileUploadView.as_view(), name='upload_voice_profile'),
    path('sessions/', views.ChatSessionListView.as_view(), name='session_list'),
    path('sessions/<str:session_id>/', views.ChatSessionDetailView.as_view(), name='session_detail'),
    path('', include(router.urls)),
]