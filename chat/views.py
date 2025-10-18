from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import VoiceRecordingRequestSerializer, VoiceRecordingResponseSerializer


def chat_interface(request):
    """Render the main chat interface."""
    return render(request, 'chat/chat_interface.html')


class UploadRecordingView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    
    @extend_schema(
        summary="Upload a voice recording",
        description="Upload a voice recording to the server. Supported formats: WAV, MP3, WebM, OGG, M4A. Max file size: 10MB.",
        request=VoiceRecordingRequestSerializer,
        responses={
            201: VoiceRecordingResponseSerializer,
        },
    )
    def post(self, request):
        input_serializer = VoiceRecordingRequestSerializer(data=request.data)
        
        if input_serializer.is_valid():
            try:
                file_info = input_serializer.save(user=request.user)
                
                file_info['url'] = f"/media/{file_info['file_path']}"
                
                return Response({
                    'success': True,
                    'message': 'Recording uploaded successfully',
                    'data': file_info
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({
                    'success': False,
                    'message': 'Error saving file',
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': input_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)