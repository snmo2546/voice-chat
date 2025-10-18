from rest_framework import serializers
import os
from django.utils import timezone
from django.conf import settings


class VoiceFileInfoSerializer(serializers.Serializer):
    file_path = serializers.CharField()
    filename = serializers.CharField()
    size = serializers.FloatField()
    content_type = serializers.CharField()
    url = serializers.CharField(required=False)


class VoiceRecordingResponseSerializer(serializers.Serializer):
    """Serializer for voice recording upload response."""
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = VoiceFileInfoSerializer()


class VoiceRecordingRequestSerializer(serializers.Serializer):
    """Serializer for uploading voice recordings."""
    recording = serializers.FileField(required=True)
    session_id = serializers.CharField(required=False, allow_blank=True)
    
    def validate_recording(self, value):
        """Validate the uploaded file."""
        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise serializers.ValidationError('File size cannot exceed 10MB.')
        
        allowed_extensions = ['.wav', '.mp3', '.webm', '.ogg', '.m4a']
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f'File type not supported. Allowed types: {", ".join(allowed_extensions)}'
            )
        
        return value
    
    def save(self, user):
        """Save the uploaded recording and return the file path."""
        recording = self.validated_data['recording']
        session_id = self.validated_data.get('session_id')
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        ext = os.path.splitext(recording.name)[1]
        filename = f'recording_{timestamp}_{user.id}{ext}'
        
        file_path = f'recordings/{filename}'
        
        full_path = os.path.join(settings.MEDIA_ROOT, 'recordings', filename)
        
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'wb+') as destination:
            for chunk in recording.chunks():
                destination.write(chunk)
        
        return {
            'file_path': file_path,
            'filename': filename,
            'size': recording.size,
            'content_type': recording.content_type,
        }