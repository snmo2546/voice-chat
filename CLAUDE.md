# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Voice-chat is a Django-based web application that provides a GPT-style chat interface with voice recording capabilities. The application features a two-phase voice message flow that separates voice transcription from AI response generation, allowing for better user feedback and modular architecture. The backend uses Django REST Framework (DRF) for API endpoints, integrates with OpenAI Whisper for speech-to-text, and uses a local LLM (via Ollama) for chat responses. The frontend uses vanilla JavaScript with a modern chat UI.

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

**TTS Backend Settings:**
- `TTS_BACKEND` - TTS engine selection (piper/coqui, default: piper)
- **Piper TTS** (recommended for CPU):
  - `PIPER_DEFAULT_MODEL_PATH` - Path to .onnx model file
  - `PIPER_DEFAULT_MODEL_CONFIG` - Path to .onnx.json config file
- **Coqui TTS** (optional, for voice cloning):
  - `CLONETTS_MODEL_NAME` - TTS model name
  - `CLONETTS_OUTPUT_FORMAT` - Audio output format (wav/mp3)
  - `CLONETTS_LANGUAGE` - TTS language code

See `.env.example` for a complete template.

## Architecture Overview

### URL Routing Pattern

The project uses a clear separation between UI routes and API routes:

**UI Routes** (root level):
- `/` - Chat interface
- `/chat/` - Chat interface
- `/admin/` - Django admin panel

**API Routes** (under `/api/` prefix):
- `/api/chat/upload-recording/` - Voice recording upload and transcription
- `/api/chat/send-message/` - Unified message sending and AI response generation
- `/api/users/*` - User-related API endpoints
- `/api/docs/` - Swagger UI documentation
- `/api/schema/` - OpenAPI schema

This separation is enforced in `voice_chat/urls.py` where UI views are registered directly and API routes are included with the `/api/` prefix.

### Django Apps Structure

**chat** - Main application for chat functionality
- Models: `ChatSession`, `ChatMessage` (OpenAI-compatible message format), `AudioFile`
- Services: `WhisperService` (voice transcription), `LocalLLMService` (AI responses)
- API Views: `UploadRecordingView` (Phase 1: transcription), `SendMessageView` (Phase 2: AI response)
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

**Two-Phase Voice Message Flow**:

**Phase 1 - Voice Transcription**:
1. User clicks microphone button → MediaRecorder API starts recording
2. User clicks stop → Recording stops, `handleAudioRecorded()` is called
3. Audio blob is uploaded to `/api/chat/upload-recording/` via FormData with session_id
4. Server creates AudioFile record, calls WhisperService to transcribe
5. Server creates ChatMessage (role=USER) with transcribed text
6. Frontend displays transcribed text as user message
7. Returns `user_message` object with message ID

**Phase 2 - AI Response Generation**:
1. Frontend calls `/api/chat/send-message/` with message_id from Phase 1
2. Server retrieves message, builds conversation history (last 10 messages)
3. LocalLLMService generates response using conversation context
4. Server creates ChatMessage (role=ASSISTANT) with AI response
5. Frontend displays AI message in chat interface

**Text Message Flow**:
1. User types message and clicks send
2. Frontend calls `/api/chat/send-message/` with content field
3. Server follows Phase 2 process (creates user message + generates AI response)

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

**AudioFile**:
- Dedicated model for managing audio recordings separate from chat messages
- Tracks transcription lifecycle: PENDING → TRANSCRIBING → COMPLETED/FAILED
- Fields:
  - `file`: FileField stored in `media/recordings/`
  - `original_filename`, `file_size`, `mime_type`: File metadata
  - `duration`: Optional duration in seconds
  - `transcription_status`: Processing state tracker
  - `transcription_text`: Result of voice-to-text conversion
  - `uploaded_by`: ForeignKey to User (nullable for anonymous)
  - `uploaded_at`: Timestamp of upload

**ChatSession**:
- Tracks individual chat sessions with unique session IDs
- Maintains message count and last activity timestamp
- `update_activity()` method updates counters from related messages
- `get_display_title()` returns title or truncated session ID
- Supports both authenticated and anonymous users

**ChatMessage**:
- OpenAI-compatible message format with role choices: user, assistant, system, function
- `to_dict()` method converts to OpenAI API format
- Supports tool calls via JSONField
- Special handling for function messages (requires 'name' field)
- New `audio_file` ForeignKey links voice recordings to messages

### DRF API Endpoints

**Upload Recording** (`POST /api/chat/upload-recording/`) - Phase 1:
- View: `UploadRecordingView` (class-based APIView)
- Parsers: `MultiPartParser`, `FormParser` (required for file uploads)
- Permissions: `AllowAny` (handles both authenticated and anonymous users)
- Request Serializer: `VoiceRecordingRequestSerializer`
  - `recording`: FileField (required, max 10MB, formats: .wav, .mp3, .webm, .ogg, .m4a)
  - `session_id`: CharField (optional, allows joining existing session)
- Response Serializer: `VoiceRecordingResponseSerializer`
  - `success`: Boolean
  - `message`: Status message
  - `transcription`: The transcribed text
  - `session_id`: UUID (auto-generated or provided)
  - `user_message`: Full ChatMessageSerializer object with message ID
- Processing Flow:
  1. Creates AudioFile record
  2. Calls WhisperService to transcribe audio
  3. Creates ChatMessage (role=USER) with transcription
  4. Updates session activity
- Returns: 201 CREATED on success, 400/500 on error

**Send Message** (`POST /api/chat/send-message/`) - Phase 2:
- View: `SendMessageView` (class-based APIView)
- Permissions: `AllowAny`
- Request Serializer: `SendMessageRequestSerializer`
  - `session_id`: CharField (required)
  - `content`: CharField (optional, for text messages)
  - `message_id`: IntegerField (optional, for voice messages already transcribed)
  - Validation: Either `content` OR `message_id` required (XOR logic)
- Response Serializer: `SendMessageResponseSerializer`
  - `success`: Boolean
  - `message`: Status message
  - `session_id`: UUID
  - `assistant_message`: Full ChatMessageSerializer object
- Processing Flow:
  1. Retrieves/creates user message by ID or content
  2. Fetches conversation history (last 10 messages)
  3. Calls LocalLLMService with context
  4. Creates ChatMessage (role=ASSISTANT)
  5. Updates session activity
- Returns: 200 OK on success, 404 if session/message not found, 400/500 on error

**Anonymous User Handling**:
```python
user = request.user if request.user.is_authenticated else None
```
Sessions and messages support null user field for anonymous chat.

### Frontend-Backend Integration

**CSRF Token Handling**:
- Template includes `{% csrf_token %}` to set cookie
- JavaScript reads cookie via `getCsrfToken()` helper
- Token sent in `X-CSRFToken` header for all POST requests

**Voice Message Upload**:
```javascript
const formData = new FormData();
formData.append('recording', audioBlob, `recording_${Date.now()}.webm`);
if (this.sessionId) {
    formData.append('session_id', this.sessionId);
}

const response = await fetch('/api/chat/upload-recording/', {
    method: 'POST',
    headers: { 'X-CSRFToken': this.getCsrfToken() },
    body: formData,
});

const data = await response.json();
// data contains: transcription, session_id, user_message (with ID)
```

**AI Response Request**:
```javascript
const response = await fetch('/api/chat/send-message/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.getCsrfToken()
    },
    body: JSON.stringify({
        session_id: this.sessionId,
        message_id: userMessage.id  // OR content: "text message"
    })
});

const data = await response.json();
// data contains: assistant_message with AI response
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

### AI Services

**WhisperService** (`chat/services.py`):
- Lazy-loads OpenAI Whisper model on first use (cached in class variable)
- `transcribe(audio_file_path)` method:
  - Input: Absolute path to audio file
  - Output: Dict with `text`, `language`, `segments`
  - Model size configurable via `settings.WHISPER_MODEL_SIZE` (default: 'base')
- Used by UploadRecordingView to convert speech to text

**LocalLLMService** (`chat/services.py`):
- Interface to local LLM via Ollama API
- `generate_response(prompt, conversation_history, stream=False)`:
  - Appends user prompt to conversation history
  - Posts to `settings.LOCAL_LLM_ENDPOINT` (default: http://localhost:11434/api/chat)
  - Timeout: `settings.LOCAL_LLM_TIMEOUT` (120 seconds)
  - Uses model: `settings.LOCAL_LLM_MODEL` (default: 'deepseek-r1:8b')
  - Returns string response from LLM

**CloneTTSService** (`chat/services.py`):
- Text-to-Speech service using Coqui TTS with XTTS v2 for voice cloning
- Lazy-loads TTS model on first use (cached in class variable)
- Auto-detects GPU/CPU and uses appropriate device
- `synthesize_speech(text, voice_id='default', speaker_wav=None)`:
  - Input: Text to synthesize, optional voice ID, optional reference audio path
  - Output: Dict with `audio_bytes`, `generation_time`, `file_size`, `mime_type`
  - Requires reference audio file (6-30 seconds recommended) for voice cloning
  - Falls back to default voice if no speaker_wav provided
- `synthesize_with_default_voice(text)`: Convenience method using system default voice
- Configuration in settings.py:
```python
LOCAL_LLM_ENDPOINT = 'http://localhost:11434/api/chat'
LOCAL_LLM_MODEL = 'deepseek-r1:8b'
LOCAL_LLM_TIMEOUT = 120  # seconds
WHISPER_MODEL_SIZE = 'base'  # tiny, base, small, medium, large

# TTS Settings (Coqui TTS with XTTS v2)
CLONETTS_MODEL_NAME = 'tts_models/multilingual/multi-dataset/xtts_v2'
CLONETTS_OUTPUT_FORMAT = 'wav'  # Options: wav, mp3
CLONETTS_LANGUAGE = 'en'  # Language code
CLONETTS_DEFAULT_SPEAKER_WAV = BASE_DIR / 'media' / 'voice_profiles' / 'default_voice.wav'
```

### Session Management

**Frontend Session Tracking**:
- VoiceChat class maintains `sessionId` variable
- Auto-generates UUID v4 on first message if not provided
- Passes `session_id` with every API request
- Persists across multiple messages in same conversation
- Reset on "New Chat" button click

**Backend Session Handling**:
- ChatSession model uses unique session_id (string UUID)
- Created on-demand when first message is sent
- `update_activity()` method updates timestamp and message count
- Supports both authenticated users and anonymous sessions

### Django Admin Customization

Admin classes in `chat/admin.py` use custom display methods and are marked read-only to prevent manual data entry:
- `has_add_permission()` returns `False` to disable creation
- Custom list displays with badges, previews, and clickable links
- Sessions and messages should be created programmatically, not via admin

**ChatSessionAdmin**:
- Displays session_id, title, user, message_count, last_activity
- Organized fieldsets for Session Information, Statistics, and Timestamps

**ChatMessageAdmin**:
- Role badge with color coding (Blue=User, Green=Assistant, Orange=System, Purple=Function)
- Content preview (truncated to 80 chars)
- Clickable session link to parent session
- Audio indicator with link to associated AudioFile
- Tool calls in collapsible section

**AudioFileAdmin**:
- File size in human-readable format (B, KB, MB, GB, TB)
- Duration displayed as MM:SS format
- Status badge with color coding (Gray=Pending, Blue=Transcribing, Green=Completed, Red=Failed)
- Filterable by status, mime type, date, uploader
- Searchable by filename, transcription text, uploader username

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

## External Services Setup

**Ollama (Local LLM)**:
```bash
# Install Ollama from https://ollama.ai

# Pull the model specified in settings
ollama pull deepseek-r1:8b

# Run Ollama server (default: localhost:11434)
ollama serve
```

**Whisper (Voice Transcription)**:
- Automatically downloads on first use
- Model size configurable in settings.py
- Requires sufficient RAM (base model ~1GB, large model ~3GB)

**Coqui TTS (Voice Synthesis - Optional)**:
```bash
# Already included in requirements.txt
pip install TTS torch torchaudio

# Download XTTS v2 model (automatic on first use, ~2GB)
# Model will download to ~/.local/share/tts/

# Test TTS installation
python -c "from TTS.api import TTS; print(TTS().list_models())"

# Note: Coqui TTS is CPU-intensive. Use Piper TTS for faster CPU performance.
```

**Piper TTS (Voice Synthesis - Recommended for CPU)**:
```bash
# Already included in requirements.txt
pip install piper-tts

# Download voice models from GitHub releases
# https://github.com/rhasspy/piper/releases

# Example: Download en_US-lessac-medium voice
# 1. Go to https://github.com/rhasspy/piper/releases
# 2. Download both files:
#    - en_US-lessac-medium.onnx (~60MB)
#    - en_US-lessac-medium.onnx.json (~1KB)
# 3. Place in media/piper_voices/ directory

# Create directory
mkdir -p media/piper_voices

# Verify Piper installation
python -c "from piper.voice import PiperVoice; print('Piper installed successfully')"
```

**FFmpeg (Audio Conversion)**:
```bash
# Required for browser-recorded voice profiles (WebM to WAV conversion)

# Windows (using Chocolatey)
choco install ffmpeg

# Windows (manual download)
# Download from https://ffmpeg.org/download.html
# Extract and add to PATH

# Linux (Ubuntu/Debian)
sudo apt update
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Verify installation
ffmpeg -version
```

**Setting up Default Voice**:
1. Record or obtain a 6-30 second audio sample of clear speech
2. Save it as `media/voice_profiles/default_voice.wav`
3. Or upload via Admin Panel → Voice Profiles → Add Voice Profile
4. Or upload via Chat UI → Voice Settings → Manage Voices → Record/Upload tabs

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
- **Audio**: Web Audio API, MediaRecorder API, FFmpeg (audio conversion)
- **AI Services**:
  - **Speech-to-Text**: OpenAI Whisper (local inference)
  - **LLM**: Ollama with deepseek-r1:8b (local inference)
  - **Text-to-Speech**:
    - Piper TTS (default, CPU-optimized, 10-100x faster on CPU)
    - Coqui TTS with XTTS v2 (optional, voice cloning, GPU-recommended)
- **Session Management**: UUID v4-based session tracking

## Architecture Highlights

### Separation of Concerns
- **Transcription** (upload-recording) separate from **AI Response** (send-message)
- Frontend can show independent progress for each phase
- Audio file metadata tracked separately from chat messages via AudioFile model

### Conversation Context
- SendMessageView retrieves last 10 messages for context
- Messages ordered by timestamp for coherent conversation flow
- Previous messages formatted for LLM consumption

### Data Flow
```
User Action (Voice/Text)
    ↓
Frontend VoiceChat class
    ↓
[Voice Path]                    [Text Path]
Upload to /upload-recording/    Send to /send-message/
    ↓                                ↓
WhisperService.transcribe      Get/Create ChatMessage (USER)
    ↓                                ↓
AudioFile + ChatMessage (USER)  LocalLLMService.generate_response
    ↓                                ↓
Return user_message.id          ChatMessage (ASSISTANT)
    ↓                                ↓
Send to /send-message/          Return assistant_message
with message_id                      ↓
    ↓                           Display in frontend
LocalLLMService.generate_response
    ↓
ChatMessage (ASSISTANT)
    ↓
Return assistant_message
    ↓
Display in frontend
```

### Error Handling
- Graceful fallback if LLM service unavailable
- Transcription failures tracked with status codes
- User-friendly error messages in UI
- Timeout protection for long-running LLM requests (120s)
- TTS errors logged but don't block text response (auto-play may be blocked by browser)

## TTS Backend Configuration

The application supports two TTS backends with different performance characteristics:

### Backend Comparison

| Feature | Piper TTS | Coqui TTS (XTTS v2) |
|---------|-----------|---------------------|
| **Speed (CPU)** | 0.5-2 seconds | 10-60 seconds |
| **Quality** | High (neural) | Very High (neural) |
| **Voice Cloning** | No (pre-trained only) | Yes (6-30s sample) |
| **Model Size** | 20-100MB per voice | ~2GB |
| **Best For** | CPU servers, fast response | GPU servers, custom voices |

### Selecting Backend

**Global Setting** (`.env`):
```bash
TTS_BACKEND=piper  # or 'coqui'
```

**Per-Voice Override**:
- Each VoiceProfile has a `tts_backend` field
- Automatically set based on uploaded file type:
  - `.onnx` + `.json` → Piper
  - `.wav/.mp3/.webm` → Coqui
- Voice profile's backend overrides global setting

### Quick Start with Piper

1. Download a voice model from https://github.com/rhasspy/piper/releases
2. Place files in `media/piper_voices/`:
   - `en_US-lessac-medium.onnx`
   - `en_US-lessac-medium.onnx.json`
3. Set in `.env`:
   ```bash
   TTS_BACKEND=piper
   PIPER_DEFAULT_MODEL_PATH=media/piper_voices/en_US-lessac-medium.onnx
   PIPER_DEFAULT_MODEL_CONFIG=media/piper_voices/en_US-lessac-medium.onnx.json
   ```
4. Restart server - TTS now 10-100x faster!

## Voice Profile Management

### Models

**VoiceProfile** (`chat/models.py`):
- Stores voice profiles for both TTS backends
- Fields:
  - `voice_id` (UUID), `name`, `tts_backend` (piper/coqui)
  - `is_default`, `user`, `created_at`
  - **Coqui**: `reference_audio` (FileField for voice cloning)
  - **Piper**: `piper_model_file` (.onnx), `piper_config_file` (.json)
- `voice_id` auto-generated on save if not provided
- Only one default voice per user (auto-enforced on save)
- System default voice has `user=None`

**TTSAudioFile** (`chat/models.py`):
- Stores generated TTS audio files
- OneToOne relationship with ChatMessage
- Fields: `file` (to media/tts_responses/), `message`, `voice_profile`, `file_size`, `duration`, `mime_type`, `generation_time`, `generated_at`
- Tracks which voice was used and performance metrics

### API Endpoints

**GET /api/chat/voice-profiles/**:
- Lists available voice profiles (system default + user's custom voices)
- Response: `{ success, count, voice_profiles: [VoiceProfileSerializer] }`
- Authenticated users see their custom voices + system defaults
- Anonymous users see only system defaults

**POST /api/chat/upload-voice-profile/**:
- Upload custom voice profile (supports both Coqui and Piper backends)
- Request: FormData with `name`, `set_as_default` (bool), and EITHER:
  - **Coqui**: `reference_audio` (file, 6-30 seconds recommended)
    - Formats: .wav, .mp3, .flac, .ogg, .m4a, .webm
    - Max size: 50MB
    - **WebM Conversion**: Auto-converted to WAV using ffmpeg
  - **Piper**: `piper_model` (.onnx) + `piper_config` (.onnx.json)
    - Model max size: 200MB
    - Config max size: 1MB
- Backend auto-detected from file types
- Response: `{ success, message, voice_profile: VoiceProfileSerializer }`
- VoiceProfileSerializer includes: `tts_backend`, `reference_audio_url`, `piper_model_url`, `piper_config_url`

**POST /api/chat/send-message/** (Updated):
- Now automatically generates TTS audio for AI responses
- Retrieves user's default voice or falls back to system default
- TTS generation happens after LLM response
- TTS failures logged but don't block response
- Response includes `assistant_message.tts_audio` with audio URL and metadata

### Frontend Integration

**Voice Settings UI**:
- "Manage Voices" button in sidebar opens modal
- Modal displays:
  - List of available voice profiles with badges for default voice
  - **Tabbed interface** for creating voice profiles:
    - **Record Tab**: Browser-based voice recording (MediaRecorder API)
      - Real-time recording timer
      - Audio preview before saving
      - Records as WebM, auto-converted to WAV on server
    - **Upload Tab**: Traditional file upload
  - Voice name, "set as default" checkbox
- Auto-reloads profile list after upload/recording

**TTS Auto-Play**:
- AI responses with TTS audio automatically display audio player
- Audio player shows voice name and playback controls
- Auto-play attempted (may be blocked by browser policy)
- Styled audio container with voice label
- Falls back to manual play if auto-play blocked

**JavaScript Methods** (`chat.js`):
- `openVoiceSettings()`: Show voice modal and load profiles
- `loadVoiceProfiles()`: Fetch and display available voices via API
- `switchTab(tab)`: Switch between Record and Upload tabs
- `startVoiceProfileRecording()`: Start MediaRecorder for voice recording
- `stopVoiceProfileRecording()`: Stop recording and show preview
- `saveRecordedVoiceProfile(event)`: Upload recorded WebM audio to backend
- `uploadVoiceProfile(event)`: Handle file upload form submission
- `addMessage(role, content, ttsAudio)`: Enhanced to display TTS audio player

### Admin Panel

**VoiceProfileAdmin**:
- Display: name, voice_id (shortened), default badge, user, reference audio link
- Filterable by is_default, created_at, user
- Searchable by name, voice_id, username
- Reference audio playable via link

**TTSAudioFileAdmin**:
- Display: message link, voice name, file size, duration, generation time
- Filterable by generated_at, voice_profile
- Searchable by message content, voice profile name
- Performance metrics visible

### TTS Workflow

```
1. User sends message (text or voice)
   ↓
2. LLM generates text response
   ↓
3. Create ChatMessage (role=assistant)
   ↓
4. Auto-generate TTS:
   a. Get user's default voice or system default
   b. CloneTTSService.synthesize_speech(text, speaker_wav)
   c. Save audio as TTSAudioFile linked to ChatMessage
   d. Log errors but don't fail if TTS generation fails
   ↓
5. Return ChatMessage with tts_audio field populated
   ↓
6. Frontend displays text + audio player
   ↓
7. Browser auto-plays audio (if allowed)
```

### Media Storage

- Voice profiles stored in: `media/voice_profiles/`
- TTS audio stored in: `media/tts_responses/`
- Naming convention: `tts_{message_id}_{timestamp}.wav`
- Voice profiles permanent, TTS audio permanent (consider cleanup policy)

### Performance Considerations

- TTS generation: 2-10 seconds depending on text length and hardware
- GPU significantly faster than CPU for TTS
- Model loads once and stays in memory (~2GB VRAM/RAM)
- Audio files: ~100-500KB per response
- Consider async TTS generation for better UX (future improvement)
