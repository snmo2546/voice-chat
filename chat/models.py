from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


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
        self.message_count = self.messages.filter(is_deleted=False).count()
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