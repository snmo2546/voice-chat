from django.contrib import admin
from django.utils.html import format_html
from .models import ChatSession, ChatMessage, AudioFile, VoiceProfile, TTSAudioFile


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'title', 'user', 'message_count', 'last_activity', 'created_at']
    list_filter = ['created_at', 'last_activity', 'user']
    search_fields = ['session_id', 'title', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'last_activity', 'message_count']
    ordering = ['-last_activity']
    
    fieldsets = (
        ('Session Information', {
            'fields': ('session_id', 'user', 'title')
        }),
        ('Statistics', {
            'fields': ('message_count', 'last_activity')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'role_badge', 'content_preview', 'model', 'user', 'audio_indicator', 'session_link', 'timestamp']
    list_filter = ['role', 'timestamp', 'model', 'user']
    search_fields = ['content', 'session__session_id', 'user__username', 'model']
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Message Information', {
            'fields': ('role', 'content', 'model')
        }),
        ('Relationships', {
            'fields': ('session', 'user', 'audio_file')
        }),
        ('Tool Calls', {
            'fields': ('tool_calls',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )
    
    def role_badge(self, obj):
        """Display role with color coding."""
        colors = {
            'user': '#2196F3',      # Blue
            'assistant': '#4CAF50',  # Green
            'system': '#FF9800',     # Orange
            'function': '#9C27B0',   # Purple
        }
        color = colors.get(obj.role, '#757575')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.role.upper()
        )
    role_badge.short_description = 'Role'
    
    def content_preview(self, obj):
        """Display truncated content preview."""
        max_length = 80
        if len(obj.content) > max_length:
            return f'{obj.content[:max_length]}...'
        return obj.content
    content_preview.short_description = 'Content'
    
    def session_link(self, obj):
        """Create a clickable link to the session."""
        if obj.session:
            url = f'/admin/chat/chatsession/{obj.session.id}/change/'
            session_id_short = obj.session.session_id[:16] + '...' if len(obj.session.session_id) > 16 else obj.session.session_id
            return format_html('<a href="{}">{}</a>', url, session_id_short)
        return format_html('<span style="color: #999;">No Session</span>')
    session_link.short_description = 'Session'
    
    def audio_indicator(self, obj):
        """Display audio file indicator with link."""
        if obj.audio_file:
            url = f'/admin/chat/audiofile/{obj.audio_file.id}/change/'
            return format_html('<a href="{}" title="{}">🎤 Audio</a>', url, obj.audio_file.original_filename)
        return format_html('<span style="color: #999;">-</span>')
    audio_indicator.short_description = 'Audio'


@admin.register(AudioFile)
class AudioFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'original_filename', 'file_size_display', 'duration_display', 'status_badge', 'uploaded_by', 'uploaded_at']
    list_filter = ['transcription_status', 'mime_type', 'uploaded_at', 'uploaded_by']
    search_fields = ['original_filename', 'transcription_text', 'uploaded_by__username']
    readonly_fields = ['uploaded_at', 'file_size', 'mime_type', 'original_filename']
    ordering = ['-uploaded_at']
    
    fieldsets = (
        ('File Information', {
            'fields': ('file', 'original_filename', 'file_size', 'mime_type', 'duration')
        }),
        ('Transcription', {
            'fields': ('transcription_status', 'transcription_text')
        }),
        ('Metadata', {
            'fields': ('uploaded_by', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Display transcription status with color coding."""
        colors = {
            'pending': '#757575',      # Gray
            'transcribing': '#2196F3', # Blue
            'completed': '#4CAF50',    # Green
            'failed': '#F44336',       # Red
        }
        color = colors.get(obj.transcription_status, '#757575')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_transcription_status_display()
        )
    status_badge.short_description = 'Status'
    
    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f'{size:.1f} {unit}'
            size /= 1024.0
        return f'{size:.1f} TB'
    file_size_display.short_description = 'File Size'
    
    def duration_display(self, obj):
        """Display duration in human-readable format."""
        if obj.duration:
            minutes = int(obj.duration // 60)
            seconds = int(obj.duration % 60)
            return f'{minutes}:{seconds:02d}'
        return '-'
    duration_display.short_description = 'Duration'


@admin.register(VoiceProfile)
class VoiceProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'voice_id_short', 'default_badge', 'user', 'has_audio', 'created_at']
    list_filter = ['is_default', 'created_at', 'user']
    search_fields = ['name', 'voice_id', 'user__username']
    readonly_fields = ['voice_id', 'created_at']
    ordering = ['-is_default', '-created_at']
    
    fieldsets = (
        ('Voice Information', {
            'fields': ('name', 'voice_id', 'is_default')
        }),
        ('Audio Reference', {
            'fields': ('reference_audio',)
        }),
        ('Ownership', {
            'fields': ('user',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def voice_id_short(self, obj):
        """Display shortened voice ID."""
        if len(obj.voice_id) > 16:
            return f'{obj.voice_id[:16]}...'
        return obj.voice_id
    voice_id_short.short_description = 'Voice ID'
    
    def default_badge(self, obj):
        """Display default status badge."""
        if obj.is_default:
            return format_html(
                '<span style="background-color: #4CAF50; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">DEFAULT</span>'
            )
        return format_html('<span style="color: #999;">-</span>')
    default_badge.short_description = 'Default'
    
    def has_audio(self, obj):
        """Indicator for reference audio."""
        if obj.reference_audio:
            return format_html('✓ <a href="{}">Listen</a>', obj.reference_audio.url)
        return format_html('<span style="color: #999;">No audio</span>')
    has_audio.short_description = 'Reference Audio'


@admin.register(TTSAudioFile)
class TTSAudioFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'message_link', 'voice_name', 'file_size_display', 'duration_display', 'generation_time_display', 'generated_at']
    list_filter = ['generated_at', 'voice_profile']
    search_fields = ['message__content', 'voice_profile__name']
    readonly_fields = ['file_size', 'mime_type', 'generation_time', 'generated_at']
    ordering = ['-generated_at']
    
    fieldsets = (
        ('TTS Information', {
            'fields': ('message', 'voice_profile')
        }),
        ('Generated File', {
            'fields': ('file', 'file_size', 'duration', 'mime_type')
        }),
        ('Performance', {
            'fields': ('generation_time',)
        }),
        ('Metadata', {
            'fields': ('generated_at',),
            'classes': ('collapse',)
        }),
    )
    
    def message_link(self, obj):
        """Link to the associated message."""
        url = f'/admin/chat/chatmessage/{obj.message.id}/change/'
        content_preview = obj.message.content[:40] + '...' if len(obj.message.content) > 40 else obj.message.content
        return format_html('<a href="{}">{}</a>', url, content_preview)
    message_link.short_description = 'Message'
    
    def voice_name(self, obj):
        """Display voice profile name."""
        if obj.voice_profile:
            return obj.voice_profile.name
        return format_html('<span style="color: #999;">Unknown</span>')
    voice_name.short_description = 'Voice'
    
    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f'{size:.1f} {unit}'
            size /= 1024.0
        return f'{size:.1f} TB'
    file_size_display.short_description = 'File Size'
    
    def duration_display(self, obj):
        """Display duration in human-readable format."""
        if obj.duration:
            minutes = int(obj.duration // 60)
            seconds = int(obj.duration % 60)
            return f'{minutes}:{seconds:02d}'
        return '-'
    duration_display.short_description = 'Duration'
    
    def generation_time_display(self, obj):
        """Display generation time."""
        if obj.generation_time:
            return f'{obj.generation_time:.2f}s'
        return '-'
    generation_time_display.short_description = 'Generation Time'