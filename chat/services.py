"""
Services for speech-to-text transcription and LLM chat completion.
"""
import whisper
import requests
from django.conf import settings
from typing import List, Dict, Optional


class WhisperService:
    """Service for transcribing audio files using OpenAI Whisper."""
    
    _model = None
    
    @classmethod
    def get_model(cls):
        """Load and cache the Whisper model."""
        if cls._model is None:
            model_size = getattr(settings, 'WHISPER_MODEL_SIZE', 'base')
            print(f'Loading Whisper model: {model_size}')
            cls._model = whisper.load_model(model_size)
        return cls._model
    
    @classmethod
    def transcribe(cls, audio_file_path: str) -> Dict[str, any]:
        """
        Transcribe an audio file to text.
        
        Args:
            audio_file_path: Absolute path to the audio file
        
        Returns:
            Dictionary with transcription results:
            {
                'text': str,  # The transcribed text
                'language': str,  # Detected language
                'segments': list,  # Detailed segments with timestamps
            }
        """
        model = cls.get_model()
        result = model.transcribe(audio_file_path)
        
        return {
            'text': result['text'].strip(),
            'language': result.get('language', 'unknown'),
            'segments': result.get('segments', []),
        }


class LocalLLMService:
    """Service for generating responses using a local LLM via Ollama API."""
    
    @staticmethod
    def generate_response(
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        stream: bool = False
    ) -> str:
        """
        Generate a response from the local LLM.
        
        Args:
            prompt: The user's message/prompt
            conversation_history: List of previous messages [{'role': 'user'|'assistant', 'content': str}]
            stream: Whether to stream the response
        
        Returns:
            The generated response text
        """
        endpoint = getattr(settings, 'LOCAL_LLM_ENDPOINT', 'http://localhost:11434/api/chat')
        model_name = getattr(settings, 'LOCAL_LLM_MODEL', 'gpt-oss')
        
        messages = conversation_history or []
        messages.append({'role': 'user', 'content': prompt})
        
        payload = {
            'model': model_name,
            'messages': messages,
            'stream': stream,
        }
        
        try:
            timeout = getattr(settings, 'LOCAL_LLM_TIMEOUT', 120)
            response = requests.post(endpoint, json=payload, timeout=timeout)
            response.raise_for_status()
            
            result = response.json()
            
            if 'message' in result and 'content' in result['message']:
                return result['message']['content']
            
            return result.get('response', 'Sorry, I could not generate a response.')
        except requests.exceptions.RequestException as e:
            print(f"Error calling local LLM: {e}")
            return f"Error: Could not connect to local LLM. Please ensure the model is running at {endpoint}"
        except Exception as e:
            print(f"Unexpected error in LLM service: {e}")
            return "Sorry, an error occurred while generating a response."