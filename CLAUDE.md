# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Voice-chat is a Django-based web application that provides a GPT-style chat interface with voice recording capabilities. The backend uses Django REST Framework (DRF) for API endpoints, and the frontend uses vanilla JavaScript with a modern chat UI.

## Development Setup

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
# Copy .env.example to .env and update values
cp .env.example .env
# Edit .env and set your SECRET_KEY, DEBUG, ALLOWED_HOSTS, and model settings

# Run database migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser

# Run development server
python manage.py runserver

# Access points:
# - Chat UI: http://localhost:8000/ or http://localhost:8000/chat/
# - Admin Panel: http://localhost:8000/admin/
# - Swagger API Docs: http://localhost:8000/api/docs/
```

## Environment Variables

The application uses a `.env` file for configuration. Key variables:

**Django Settings:**
- `SECRET_KEY` - Django secret key (required, keep secret!)
- `DEBUG` - Debug mode (True/False)
- `ALLOWED_HOSTS` - Comma-separated list of allowed hosts

**AI Model Settings:**
- `WHISPER_MODEL_SIZE` - Whisper model size (tiny/base/small/medium/large)
- `LOCAL_LLM_ENDPOINT` - Ollama API endpoint
- `LOCAL_LLM_MODEL` - LLM model name
- `LOCAL_LLM_TIMEOUT` - Request timeout in seconds

See `.env.example` for a complete template.

## Architecture Overview

### URL Routing Pattern

The project uses a clear separation between UI routes and API routes:

**UI Routes** (root level):
- `/` - Chat interface
- `/chat/` - Chat interface
- `/admin/` - Django admin panel

**API Routes** (under `/api/` prefix):
- `/api/chat/*` - Chat-related API endpoints
- `/api/users/*` - User-related API endpoints
- `/api/docs/` - Swagger UI documentation
- `/api/schema/` - OpenAPI schema

This separation is enforced in `voice_chat/urls.py` where UI views are registered directly and API routes are included with the `/api/` prefix.

### Django Apps Structure

**chat** - Main application for chat functionality
- Models: `ChatSession`, `ChatMessage` (OpenAI-compatible message format)
- Voice recording upload API endpoint
- Chat interface UI (templates + static files)
- DRF serializers for API requests/responses

**users** - User management application (currently minimal)
- Uses Django's built-in User model
- Reserved for future user-related features

**voice_chat** - Project configuration
- Main settings and URL configuration
- Static and media file configuration

### Frontend Architecture

**Template Location**: `chat/templates/chat/chat_interface.html`
- Single-page chat interface
- CSRF token included for API calls

**Static Files**:
- CSS: `chat/static/chat/css/chat.css` - ChatGPT-inspired styling
- JS: `chat/static/chat/js/chat.js` - Voice recording and chat functionality

**Voice Recording Flow**:
1. User clicks microphone button → MediaRecorder API starts recording
2. User clicks stop → Recording stops, `handleAudioRecorded()` is called
3. Audio blob is uploaded to `/api/chat/upload-recording/` via FormData
4. CSRF token is included in request headers via `getCsrfToken()` method
5. Server saves file to `media/recordings/` and returns file metadata

### Media File Handling

**Configuration** (in `voice_chat/settings.py`):
```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

**Voice Recording Storage**:
- Path: `media/recordings/`
- Naming: `recording_YYYYMMDD_HHMMSS_[user_id].ext`
- For anonymous users: user_id is 'anonymous'
- Supported formats: WAV, MP3, WebM, OGG, M4A
- Max size: 10MB

**Important**: File paths in responses use forward slashes (`recordings/file.mp3`) for URL compatibility, but file system operations use `os.path.join()` with `settings.MEDIA_ROOT`.

## Key Components

### Chat Models

**ChatSession**:
- Tracks individual chat sessions with unique session IDs
- Maintains message count and last activity timestamp
- `update_activity()` method updates counters from related messages

**ChatMessage**:
- OpenAI-compatible message format with role choices: user, assistant, system, function
- `to_dict()` method converts to OpenAI API format
- Supports tool calls via JSONField
- Special handling for function messages (requires 'name' field)

### DRF API Endpoints

**Upload Recording** (`POST /api/chat/upload-recording/`):
- View: `UploadRecordingView` (class-based APIView)
- Parsers: `MultiPartParser`, `FormParser` (required for file uploads)
- Permissions: `AllowAny` (handles both authenticated and anonymous users)
- Serializers:
  - Request: `VoiceRecordingRequestSerializer` (validates file type and size)
  - Response: `VoiceRecordingResponseSerializer` (structured success/error response)

**Anonymous User Handling**:
```python
user = request.user if request.user.is_authenticated else type('obj', (object,), {'id': 'anonymous'})()
```

### Frontend-Backend Integration

**CSRF Token Handling**:
- Template includes `{% csrf_token %}` to set cookie
- JavaScript reads cookie via `getCsrfToken()` helper
- Token sent in `X-CSRFToken` header for all POST requests

**File Upload**:
```javascript
const formData = new FormData();
formData.append('recording', audioBlob, `recording_${Date.now()}.webm`);

fetch('/api/chat/upload-recording/', {
    method: 'POST',
    headers: { 'X-CSRFToken': this.getCsrfToken() },
    body: formData,
});
```

## Important Patterns and Conventions

### File Path Handling

**Critical**: Due to Claude Code file modification behavior on Windows, always use complete absolute Windows paths with drive letters and backslashes for ALL file operations when editing files:
- ✅ `C:\Users\snmo2\Jacky-Chen\voice-chat\chat\views.py`
- ❌ `chat/views.py`

However, for URL paths in responses and frontend code, use forward slashes for cross-platform compatibility.

### Serializer Validation

DRF automatically calls `validate_<field_name>()` methods during `is_valid()`:
- `validate_recording()` is auto-called for the `recording` field
- Must return the value (potentially modified)
- Raise `serializers.ValidationError` for invalid data

### Django Admin Customization

Admin classes in `chat/admin.py` use custom display methods and are marked read-only to prevent manual data entry:
- `has_add_permission()` returns `False` to disable creation
- Custom list displays with badges, previews, and clickable links
- Sessions and messages should be created programmatically, not via admin

## Common Commands

```bash
# Database operations
python manage.py makemigrations
python manage.py migrate
python manage.py migrate chat zero  # Rollback chat app migrations

# Development server
python manage.py runserver

# Create admin user
python manage.py createsuperuser

# Django shell for debugging
python manage.py shell

# Check for issues
python manage.py check

# Collect static files (for production)
python manage.py collectstatic
```

## API Documentation

This project uses **drf-spectacular** for automatic OpenAPI schema generation.

**Access Swagger UI**: http://localhost:8000/api/docs/

The Swagger UI provides:
- Interactive API testing
- Request/response schemas
- File upload interface for voice recordings
- Authentication testing

All API views decorated with `@extend_schema()` are automatically documented.

## Tech Stack

- **Backend**: Django 5.2.7, Django REST Framework 3.16.1
- **API Documentation**: drf-spectacular 0.28.0
- **Database**: SQLite (development)
- **Frontend**: Vanilla JavaScript, CSS (no framework)
- **Audio**: Web Audio API, MediaRecorder API
