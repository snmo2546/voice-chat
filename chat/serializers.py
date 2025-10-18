from rest_framework import serializers
import os
from django.utils import timezone
from .models import ChatMessage, AudioFile


class AudioFileSerializer(serializers.ModelSerializer):
    """Serializer for AudioFile model."""
    url = serializers.SerializerMethodField()
    
    class Meta:
        model = AudioFile
        fields = [
            'id',
            'original_filename',
            'file_size',
            'mime_type',
            'duration',
            'transcription_status',
            'transcription_text',
            'uploaded_at',
            'url'
        ]
        read_only_fields = ['id', 'uploaded_at']
    
    def get_url(self, obj):
        """Get the URL to access the file."""
        return obj.get_file_url()


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for ChatMessage model."""
    audio_file = AudioFileSerializer(read_only=True)
    
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'timestamp', 'model', 'audio_file']
        read_only_fields = ['id', 'timestamp']


class VoiceRecordingResponseSerializer(serializers.Serializer):
    """Serializer for voice recording upload response."""
    success = serializers.BooleanField()
    message = serializers.CharField()
    transcription = serializers.CharField(required=False)
    session_id = serializers.CharField(required=False)
    user_message = ChatMessageSerializer(required=False)
    assistant_message = ChatMessageSerializer(required=False)


class SendMessageRequestSerializer(serializers.Serializer):
    """Serializer for sending messages to get AI responses."""
    session_id = serializers.CharField(required=True, help_text='Chat session ID')
    content = serializers.CharField(required=False, allow_blank=False, help_text='Message content for text messages')
    message_id = serializers.IntegerField(required=False, help_text='Existing message ID for voice messages')
    
    def validate(self, data):
        """Ensure either content or message_id is provided."""
        if not data.get('content') and not data.get('message_id'):
            raise serializers.ValidationError(
                "Either 'content' (for text messages) or 'message_id' (for voice messages) is required"
            )
        
        if data.get('content') and data.get('message_id'):
            raise serializers.ValidationError(
                "Provide either 'content' or 'message_id', not both"
            )
        
        return data


class SendMessageResponseSerializer(serializers.Serializer):
    """Serializer for send message response."""
    success = serializers.BooleanField()
    message = serializers.CharField()
    session_id = serializers.CharField(required=False)
    assistant_message = ChatMessageSerializer(required=False, help_text='AI response')
    error = serializers.CharField(required=False)


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
        """Save the uploaded recording and create an AudioFile instance."""
        recording = self.validated_data['recording']
        
        audio_file = AudioFile(
            original_filename=recording.name,
            file_size=recording.size,
            mime_type=recording.content_type or 'audio/unknown',
            uploaded_by=user if hasattr(user, 'pk') else None,
            transcription_status=AudioFile.PENDING
        )
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        ext = os.path.splitext(recording.name)[1]
        user_id = user.id if hasattr(user, 'id') else 'anonymous'
        filename = f'recording_{timestamp}_{user_id}{ext}'
        
        try:
            audio_file.file.save(filename, recording, save=True)
            return audio_file
        except (IOError, OSError) as e:
            # Handle file system errors (disk full, permissions, etc.)
            raise serializers.ValidationError(
                f'Failed to save audio file: {str(e)}'
            )
        except Exception as e:
            raise serializers.ValidationError(
                f'Unexpected error saving audio file: {str(e)}'
            )