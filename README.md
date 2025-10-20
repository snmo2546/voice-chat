# Voice Chat

A Django-based web application that provides a ChatGPT-style interface with voice recording capabilities. Chat with AI using your voice or text, and get audio responses back.

## Features

- **Voice & Text Chat**: Send messages via voice recording or text input
- **AI-Powered Responses**: Uses local LLM (Ollama) for intelligent conversations
- **Speech-to-Text**: Automatic voice transcription with OpenAI Whisper
- **Text-to-Speech**: AI responses read aloud with customizable voices
  - **Piper TTS**: Fast, CPU-optimized (recommended)
  - **Coqui TTS**: High-quality voice cloning with GPU support
- **Custom Voice Profiles**: Clone voices with 6-30 second audio samples
- **Session Management**: Conversation history and context awareness
- **Anonymous Chat**: No login required to start chatting

## Quick Start

### Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai) (for local LLM)
- FFmpeg (for audio conversion)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd voice-chat
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and set your SECRET_KEY and other settings
   ```

5. **Set up database**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser  # Optional: for admin access
   ```

6. **Download Piper TTS voice model** (recommended)
   - Visit [Piper Releases](https://github.com/rhasspy/piper/releases)
   - Download a voice model (e.g., `en_US-lessac-medium.onnx` and `.onnx.json`)
   - Place in `media/piper_voices/`
   - Update `.env` with model paths

7. **Start Ollama server**
   ```bash
   ollama pull deepseek-r1:8b
   ollama serve
   ```

8. **Run the application**
   ```bash
   python manage.py runserver
   ```

9. **Open your browser**
   - Chat UI: http://localhost:8000/
   - Admin Panel: http://localhost:8000/admin/
   - API Docs: http://localhost:8000/api/docs/
