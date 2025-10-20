from rest_framework import serializers
import os
from django.utils import timezone
from .models import ChatMessage, AudioFile, VoiceProfile, TTSAudioFile


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
            'speech_analysis',
            'analysis_status',
            'uploaded_at',
            'url'
        ]
        read_only_fields = ['id', 'uploaded_at']
    
    def get_url(self, obj):
        """Get the URL to access the file."""
        return obj.get_file_url()


class TTSAudioFileSerializer(serializers.ModelSerializer):
    """Serializer for TTSAudioFile model."""
    url = serializers.SerializerMethodField()
    voice_name = serializers.SerializerMethodField()
    
    class Meta:
        model = TTSAudioFile
        fields = [
            'id',
            'file_size',
            'duration',
            'mime_type',
            'generation_time',
            'generated_at',
            'url',
            'voice_name'
        ]
        read_only_fields = ['id', 'generated_at']
    
    def get_url(self, obj):
        """Get the URL to access the TTS audio file."""
        return obj.get_file_url()
    
    def get_voice_name(self, obj):
        """Get the name of the voice profile used."""
        return obj.voice_profile.name if obj.voice_profile else 'Unknown'


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for ChatMessage model."""
    audio_file = AudioFileSerializer(read_only=True)
    tts_audio = TTSAudioFileSerializer(read_only=True)
    
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'timestamp', 'model', 'audio_file', 'tts_audio']
        read_only_fields = ['id', 'timestamp']


class VoiceRecordingResponseSerializer(serializers.Serializer):
    """Serializer for voice recording upload response."""
    success = serializers.BooleanField()
    message = serializers.CharField()
    transcription = serializers.CharField(required=False)
    session_id = serializers.CharField(required=False)
    user_message = ChatMessageSerializer(required=False)
    assistant_message = ChatMessageSerializer(required=False)
    speech_analysis = serializers.JSONField(required=False)


class SendMessageRequestSerializer(serializers.Serializer):
    """Serializer for sending messages to get AI responses."""
    session_id = serializers.CharField(required=True, help_text='Chat session ID')
    content = serializers.CharField(required=False, allow_blank=False, help_text='Message content for text messages')
    message_id = serializers.IntegerField(required=False, help_text='Existing message ID for voice messages')
    speed_mode = serializers.ChoiceField(
        choices=['fast', 'quality'],
        default='fast',
        required=False,
        help_text='TTS speed mode: "fast" (OpenVoice, 2-3s) or "quality" (XTTS v2, 15-30s)'
    )
    
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
    speed_mode = serializers.CharField(required=False, help_text='TTS speed mode used (fast/quality)')
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


class VoiceProfileSerializer(serializers.ModelSerializer):
    """Serializer for VoiceProfile model."""
    reference_audio_url = serializers.SerializerMethodField()
    piper_model_url = serializers.SerializerMethodField()
    piper_config_url = serializers.SerializerMethodField()
    is_system_default = serializers.SerializerMethodField()
    
    class Meta:
        model = VoiceProfile
        fields = [
            'id',
            'voice_id',
            'name',
            'tts_backend',
            'is_default',
            'is_system_default',
            'reference_audio_url',
            'piper_model_url',
            'piper_config_url',
            'created_at'
        ]
        read_only_fields = ['id', 'voice_id', 'created_at']
    
    def get_reference_audio_url(self, obj):
        """Get the URL to access the reference audio file."""
        if obj.reference_audio:
            return obj.reference_audio.url
        return None
    
    def get_piper_model_url(self, obj):
        """Get the URL to access the Piper model file."""
        if obj.piper_model_file:
            return obj.piper_model_file.url
        return None
    
    def get_piper_config_url(self, obj):
        """Get the URL to access the Piper config file."""
        if obj.piper_config_file:
            return obj.piper_config_file.url
        return None
    
    def get_is_system_default(self, obj):
        """Check if this is a system voice (no user associated)."""
        return obj.user is None


class VoiceProfileUploadSerializer(serializers.Serializer):
    """Serializer for uploading custom voice profiles (supports both Coqui and Piper backends)."""
    name = serializers.CharField(required=True, max_length=200, help_text='Display name for the voice profile')
    
    # Coqui TTS: single audio file
    reference_audio = serializers.FileField(required=False, help_text='Reference audio file for Coqui (6-30 seconds recommended)')
    
    # Piper TTS: model + config files
    piper_model = serializers.FileField(required=False, help_text='Piper ONNX model file (.onnx)')
    piper_config = serializers.FileField(required=False, help_text='Piper config file (.onnx.json)')
    
    set_as_default = serializers.BooleanField(default=False, help_text='Set this as your default voice')
    
    def validate(self, data):
        """Ensure either Coqui or Piper files are provided."""
        has_coqui = data.get('reference_audio') is not None
        has_piper = data.get('piper_model') is not None and data.get('piper_config') is not None
        
        if not has_coqui and not has_piper:
            raise serializers.ValidationError(
                "Please provide either 'reference_audio' (for Coqui TTS) or both 'piper_model' and 'piper_config' (for Piper TTS)"
            )
        
        if has_coqui and has_piper:
            raise serializers.ValidationError(
                "Please provide files for only one backend (Coqui OR Piper), not both"
            )
        
        # Validate Piper: both files required
        if data.get('piper_model') and not data.get('piper_config'):
            raise serializers.ValidationError("Piper model requires both model (.onnx) and config (.onnx.json) files")
        if data.get('piper_config') and not data.get('piper_model'):
            raise serializers.ValidationError("Piper config requires both model (.onnx) and config (.onnx.json) files")
        
        return data
    
    def validate_reference_audio(self, value):
        """Validate the uploaded reference audio file for Coqui TTS."""
        if not value:
            return value
        
        # Max size: 50MB
        max_size = 50 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError('File size cannot exceed 50MB.')
        
        # Allowed audio formats (including WebM for browser recordings)
        allowed_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.webm']
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f'File type not supported. Allowed types: {", ".join(allowed_extensions)}'
            )
        
        return value
    
    def validate_piper_model(self, value):
        """Validate the uploaded Piper model file."""
        if not value:
            return value
        
        # Max size: 200MB (Piper models can be large)
        max_size = 200 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError('Piper model file size cannot exceed 200MB.')
        
        ext = os.path.splitext(value.name)[1].lower()
        if ext != '.onnx':
            raise serializers.ValidationError('Piper model must be an .onnx file')
        
        return value
    
    def validate_piper_config(self, value):
        """Validate the uploaded Piper config file."""
        if not value:
            return value
        
        max_size = 1 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError('Piper config file size cannot exceed 1MB.')
        
        ext = os.path.splitext(value.name)[1].lower()
        if ext != '.json':
            raise serializers.ValidationError('Piper config must be a .json file')
        
        return value
    
    def save(self, user):
        """Save the voice profile (supports both Coqui and Piper backends)."""
        from django.core.files.base import ContentFile
        import tempfile
        import subprocess
        
        name = self.validated_data['name']
        set_as_default = self.validated_data.get('set_as_default', False)
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        user_id = user.id if hasattr(user, 'id') else 'anonymous'
        
        # Determine backend based on provided files
        has_coqui = self.validated_data.get('reference_audio') is not None
        has_piper = self.validated_data.get('piper_model') is not None
        
        voice_profile = VoiceProfile(
            name=name,
            is_default=set_as_default,
            tts_backend='coqui' if has_coqui else 'piper',
            user=user if hasattr(user, 'pk') else None
        )
        
        if has_piper:
            piper_model = self.validated_data['piper_model']
            piper_config = self.validated_data['piper_config']
            
            model_filename = f'piper_{timestamp}_{user_id}.onnx'
            voice_profile.piper_model_file.save(model_filename, piper_model, save=False)
            
            config_filename = f'piper_{timestamp}_{user_id}.onnx.json'
            voice_profile.piper_config_file.save(config_filename, piper_config, save=False)
            
            voice_profile.save()
        
        else:
            reference_audio = self.validated_data['reference_audio']
            ext = os.path.splitext(reference_audio.name)[1].lower()
            
            if ext == '.webm':
                try:
                    # Create temporary files
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_webm:
                        # Write uploaded WebM
                        for chunk in reference_audio.chunks():
                            temp_webm.write(chunk)
                        temp_webm_path = temp_webm.name
                    
                    temp_wav_path = tempfile.mktemp(suffix='.wav')
                    
                    subprocess.run([
                        'ffmpeg', '-i', temp_webm_path,
                        '-acodec', 'pcm_s16le',
                        '-ar', '22050',
                        '-ac', '1',
                        temp_wav_path
                    ], check=True, capture_output=True)
                    
                    with open(temp_wav_path, 'rb') as wav_file:
                        wav_content = wav_file.read()
                    
                    os.unlink(temp_webm_path)
                    os.unlink(temp_wav_path)
                    
                    filename = f'voice_{timestamp}_{user_id}.wav'
                    voice_profile.reference_audio.save(filename, ContentFile(wav_content), save=True)
                
                except subprocess.CalledProcessError as e:
                    raise serializers.ValidationError(
                        f'Failed to convert WebM to WAV. Error: {e.stderr.decode()}'
                    )
                except FileNotFoundError:
                    raise serializers.ValidationError(
                        'ffmpeg not found. Please install ffmpeg to convert WebM files.'
                    )
                except Exception as e:
                    raise serializers.ValidationError(
                        f'Error converting audio file: {str(e)}'
                    )
            else:
                filename = f'voice_{timestamp}_{user_id}{ext}'
                try:
                    voice_profile.reference_audio.save(filename, reference_audio, save=True)
                except (IOError, OSError) as e:
                    raise serializers.ValidationError(
                        f'Failed to save reference audio: {str(e)}'
                    )
                except Exception as e:
                    raise serializers.ValidationError(
                        f'Unexpected error saving voice profile: {str(e)}'
                    )
        
        return voice_profile