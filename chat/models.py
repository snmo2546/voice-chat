from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import uuid


class VoiceProfile(models.Model):
    """Model to manage voice profiles for TTS (text-to-speech) - supports both Piper and Coqui backends."""
    
    TTS_BACKEND_CHOICES = [
        ('piper', 'Piper TTS'),
        ('coqui', 'Coqui TTS'),
    ]
    
    voice_id = models.CharField(max_length=100, unique=True, db_index=True, help_text='Unique identifier for the voice')
    name = models.CharField(max_length=200, help_text='Display name for the voice (e.g., "Default AI Voice", "My Voice")')
    
    # TTS backend selection
    tts_backend = models.CharField(
        max_length=20,
        choices=TTS_BACKEND_CHOICES,
        default='piper',
        help_text='TTS engine to use for this voice'
    )
    
    # Coqui TTS fields (voice cloning)
    reference_audio = models.FileField(
        upload_to='voice_profiles/',
        null=True,
        blank=True,
        help_text='Reference audio file for Coqui voice cloning'
    )
    
    # Piper TTS fields (pre-trained models)
    piper_model_file = models.FileField(
        upload_to='piper_voices/',
        null=True,
        blank=True,
        help_text='Piper ONNX model file (.onnx)'
    )
    piper_config_file = models.FileField(
        upload_to='piper_voices/',
        null=True,
        blank=True,
        help_text='Piper model config file (.onnx.json)'
    )
    
    is_default = models.BooleanField(default=False, help_text='Whether this is the default system voice')
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='voice_profiles',
        help_text='User who owns this voice profile (null for system default)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        default_label = ' (Default)' if self.is_default else ''
        backend_label = f' [{self.get_tts_backend_display()}]'
        return f'{self.name}{default_label}{backend_label}'
    
    def save(self, *args, **kwargs):
        # Auto-generate voice_id if not set
        if not self.voice_id:
            self.voice_id = str(uuid.uuid4())
        
        # Ensure only one default voice exists per user
        if self.is_default:
            if self.user:
                VoiceProfile.objects.filter(user=self.user, is_default=True).update(is_default=False)
            else:
                VoiceProfile.objects.filter(user__isnull=True, is_default=True).update(is_default=False)
        
        super().save(*args, **kwargs)


class AudioFile(models.Model):
    """Model to store audio file metadata and manage recordings."""
    PENDING = 'pending'
    TRANSCRIBING = 'transcribing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    
    TRANSCRIPTION_STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (TRANSCRIBING, 'Transcribing'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
    ]
    
    ANALYSIS_STATUS_CHOICES = [
        (PENDING, 'Pending'),
        ('analyzing', 'Analyzing'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
    ]
    
    file = models.FileField(upload_to='recordings/', help_text='Audio file')
    original_filename = models.CharField(max_length=255, help_text='Original filename from upload')
    file_size = models.IntegerField(help_text='File size in bytes')
    mime_type = models.CharField(max_length=50, help_text='MIME type (e.g., audio/webm)')
    duration = models.FloatField(null=True, blank=True, help_text='Duration in seconds')
    transcription_status = models.CharField(
        max_length=20,
        choices=TRANSCRIPTION_STATUS_CHOICES,
        default=PENDING,
        help_text='Current transcription processing status'
    )
    transcription_text = models.TextField(blank=True, null=True, help_text='Transcribed text content')
    
    speech_analysis = models.JSONField(
        null=True,
        blank=True,
        help_text='Speech characteristic analysis results (confidence, stability, warmth)'
    )
    analysis_status = models.CharField(
        max_length=20,
        choices=ANALYSIS_STATUS_CHOICES,
        default=PENDING,
        help_text='Status of speech analysis'
    )
    analysis_error = models.TextField(
        null=True,
        blank=True,
        help_text='Error message if analysis failed'
    )
    
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_audio_files',
        help_text='User who uploaded the file'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f'{self.original_filename} ({self.get_transcription_status_display()})'
    
    def get_file_url(self):
        """Get the URL to access the file."""
        if self.file:
            return self.file.url
        return None


class ChatSession(models.Model):
    """Model to manage chat sessions with AI-generated tags."""
    
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(default=timezone.now)
    message_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-last_activity']
    
    def __str__(self):
        return f'Session {self.session_id[:8]}... ({self.message_count} messages)'
    
    def get_display_title(self):
        """Get display title, fallback to truncated first message if no title set."""
        if self.title:
            return self.title
        return f'Session {self.session_id[:8]}...'
    
    def update_activity(self):
        """Update last activity timestamp and message count."""
        self.last_activity = timezone.now()
        self.message_count = self.messages.count()
        self.save()


class ChatMessage(models.Model):
    USER = 'user'
    ASSISTANT = 'assistant'
    SYSTEM = 'system'
    FUNCTION = 'function'
    
    ROLE_CHOICES = [
        (USER, 'User'),
        (ASSISTANT, 'Assistant'),
        (SYSTEM, 'System'),
        (FUNCTION, 'Function'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='chat_messages', null=True, blank=True)
    tool_calls = models.JSONField(blank=True, null=True)
    audio_file = models.ForeignKey(
        AudioFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_messages',
        help_text='Associated audio recording file'
    )
    
    class Meta:
        ordering = ['-timestamp']
    
    def to_dict(self):
        result = {
            'role': self.role,
            'content': self.content
        }
        
        if self.tool_calls:
            result['tool_calls'] = self.tool_calls
        
        # OpenAI requires 'name' field for function messages
        if self.role == self.FUNCTION:
            # Try to extract function name from model field (format: "tool_function_name")
            if self.model and self.model.startswith('tool_'):
                result['name'] = self.model[5:]
            else:
                try:
                    import json
                    content_data = json.loads(self.content)
                    function_name = content_data.get('function_name', 'unknown_function')
                    result['name'] = function_name
                except (json.JSONDecodeError, AttributeError):
                    result['name'] = 'unknown_function'
        
        return result


class TTSAudioFile(models.Model):
    """Model to store TTS-generated audio files for AI responses."""
    
    file = models.FileField(upload_to='tts_responses/', help_text='Generated TTS audio file')
    message = models.OneToOneField(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name='tts_audio',
        help_text='The chat message this audio is for'
    )
    voice_profile = models.ForeignKey(
        VoiceProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tts_audio_files',
        help_text='Voice profile used for generation'
    )
    file_size = models.IntegerField(help_text='File size in bytes')
    duration = models.FloatField(null=True, blank=True, help_text='Duration in seconds')
    mime_type = models.CharField(max_length=50, default='audio/wav', help_text='MIME type of generated audio')
    generation_time = models.FloatField(null=True, blank=True, help_text='Time taken to generate (seconds)')
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-generated_at']
    
    def __str__(self):
        return f'TTS for message {self.message.id} (voice: {self.voice_profile.name if self.voice_profile else "unknown"})'
    
    def get_file_url(self):
        """Get the URL to access the TTS audio file."""
        if self.file:
            return self.file.url
        return None