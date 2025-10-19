"""
Services for speech-to-text transcription, LLM chat completion, and text-to-speech.
"""
import whisper
import requests
import torch
import time
import os
import io
import wave
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
        
        system_prompt = {
            'role': 'system',
            'content': (
                'You are a helpful AI assistant. Follow these language rules strictly:\n'
                '- If the user writes in Chinese, respond ONLY in Chinese\n'
                '- If the user writes in English, respond ONLY in English\n'
                '- Never mix languages in a single response\n'
                '- Match the user\'s language exactly'
            )
        }
        
        messages = [system_prompt]
        if conversation_history:
            messages.extend(conversation_history)
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


class CloneTTSService:
    """Service for generating speech from text using TTS (Coqui TTS with XTTS v2)."""
    
    _model = None
    _device = None
    
    @classmethod
    def get_model(cls):
        """Load and cache the TTS model."""
        if cls._model is None:
            try:
                from TTS.api import TTS
                
                cls._device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f'Loading TTS model on device: {cls._device}')
                
                model_name = getattr(settings, 'CLONETTS_MODEL_NAME', 'tts_models/multilingual/multi-dataset/xtts_v2')
                cls._model = TTS(model_name).to(cls._device)
                
                print(f'TTS model loaded successfully: {model_name}')
            except ImportError:
                print("ERROR: TTS library not installed. Run: pip install TTS")
                raise
            except Exception as e:
                print(f"Error loading TTS model: {e}")
                raise
        
        return cls._model
    
    @classmethod
    def synthesize_speech(
        cls,
        text: str,
        voice_id: str = 'default',
        speaker_wav: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Generate speech audio from text using voice cloning.
        
        Args:
            text: The text to convert to speech
            voice_id: Voice profile identifier (not used directly, but for tracking)
            speaker_wav: Path to reference audio file for voice cloning (optional)
        
        Returns:
            Dictionary with generation results:
            {
                'audio_bytes': bytes,  # WAV audio data
                'generation_time': float,  # Time taken in seconds
                'file_size': int,  # Size in bytes
            }
        """
        start_time = time.time()
        
        try:
            model = cls.get_model()
            
            output_format = getattr(settings, 'CLONETTS_OUTPUT_FORMAT', 'wav')
            language = getattr(settings, 'CLONETTS_LANGUAGE', 'en')
            
            if not speaker_wav or not os.path.exists(speaker_wav):
                speaker_wav = getattr(settings, 'CLONETTS_DEFAULT_SPEAKER_WAV', None)
                if not speaker_wav or not os.path.exists(speaker_wav):
                    raise ValueError(
                        "No valid speaker_wav provided and no default speaker found. "
                        "Please upload a voice profile or configure CLONETTS_DEFAULT_SPEAKER_WAV."
                    )
            
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{output_format}') as tmp_file:
                output_path = tmp_file.name
            
            print(f'Generating TTS for text: "{text[:50]}..." using voice: {speaker_wav}')
            model.tts_to_file(
                text=text,
                file_path=output_path,
                speaker_wav=speaker_wav,
                language=language
            )
            
            with open(output_path, 'rb') as f:
                audio_bytes = f.read()
            
            # Clean up temporary file
            os.unlink(output_path)
            
            generation_time = time.time() - start_time
            file_size = len(audio_bytes)
            
            print(f'TTS generation completed in {generation_time:.2f}s, size: {file_size} bytes')
            
            return {
                'audio_bytes': audio_bytes,
                'generation_time': generation_time,
                'file_size': file_size,
                'mime_type': f'audio/{output_format}'
            }
        
        except Exception as e:
            generation_time = time.time() - start_time
            print(f"Error in TTS generation after {generation_time:.2f}s: {e}")
            raise
    
    @classmethod
    def synthesize_with_default_voice(cls, text: str) -> Dict[str, any]:
        """
        Convenience method to generate speech with the default system voice.
        
        Args:
            text: The text to convert to speech
        
        Returns:
            Dictionary with generation results (same as synthesize_speech)
        """
        return cls.synthesize_speech(text=text, voice_id='default', speaker_wav=None)


class PiperTTSService:
    """Service for generating speech from text using Piper TTS (fast, CPU-optimized)."""
    
    _voice_cache = {}  # Cache for loaded voice models
    
    @classmethod
    def get_voice(cls, model_path: str, config_path: Optional[str] = None):
        """
        Load and cache a Piper voice model.
        
        Args:
            model_path: Path to the .onnx model file
            config_path: Optional path to the .json config file (auto-detected if not provided)
        
        Returns:
            PiperVoice instance
        """
        # Use model_path as cache key
        cache_key = model_path
        
        if cache_key not in cls._voice_cache:
            try:
                from piper.voice import PiperVoice
                
                if not config_path:
                    config_path = f"{model_path}.json"
                
                if not os.path.exists(model_path):
                    raise FileNotFoundError(f"Piper model file not found: {model_path}")
                if not os.path.exists(config_path):
                    raise FileNotFoundError(f"Piper config file not found: {config_path}")
                
                print(f'Loading Piper voice model: {model_path}')
                voice = PiperVoice.load(model_path, config_path=config_path)
                cls._voice_cache[cache_key] = voice
                print(f'Piper voice loaded successfully')
            
            except ImportError:
                print("ERROR: piper-tts library not installed. Run: pip install piper-tts")
                raise
            except Exception as e:
                print(f"Error loading Piper voice model: {e}")
                raise
        
        return cls._voice_cache[cache_key]
    
    @classmethod
    def synthesize_speech(
        cls,
        text: str,
        voice_id: str = 'default',
        speaker_wav: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Generate speech audio from text using Piper TTS.
        
        Args:
            text: The text to convert to speech
            voice_id: Voice profile identifier (for tracking purposes)
            speaker_wav: Path to Piper model file (.onnx) or None for default
        
        Returns:
            Dictionary with generation results:
            {
                'audio_bytes': bytes,  # WAV audio data
                'generation_time': float,  # Time taken in seconds
                'file_size': int,  # Size in bytes
                'mime_type': str,  # 'audio/wav'
            }
        """
        start_time = time.time()
        
        try:
            # Determine model and config paths
            if speaker_wav and os.path.exists(speaker_wav):
                model_path = speaker_wav
                config_path = f"{model_path}.json"
            else:
                model_path = getattr(settings, 'PIPER_DEFAULT_MODEL_PATH', None)
                config_path = getattr(settings, 'PIPER_DEFAULT_MODEL_CONFIG', None)
                
                if not model_path or not os.path.exists(model_path):
                    raise ValueError(
                        "No valid Piper model provided and no default model found. "
                        "Please configure PIPER_DEFAULT_MODEL_PATH in settings or provide a model path."
                    )
            
            voice = cls.get_voice(model_path, config_path)
            
            print(f'Generating Piper TTS for text: "{text[:50]}..." using model: {model_path}')
            
            audio_chunks = []
            for audio_chunk in voice.synthesize(text):
                audio_chunks.append(audio_chunk.audio_int16_bytes)
            
            raw_audio = b''.join(audio_chunks)
            
            sample_rate = voice.config.sample_rate
            
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(raw_audio)
            
            audio_bytes = wav_io.getvalue()
            
            generation_time = time.time() - start_time
            file_size = len(audio_bytes)
            
            print(f'Piper TTS generation completed in {generation_time:.2f}s, size: {file_size} bytes')
            
            return {
                'audio_bytes': audio_bytes,
                'generation_time': generation_time,
                'file_size': file_size,
                'mime_type': 'audio/wav'
            }
        
        except Exception as e:
            generation_time = time.time() - start_time
            print(f"Error in Piper TTS generation after {generation_time:.2f}s: {e}")
            raise
    
    @classmethod
    def synthesize_with_default_voice(cls, text: str) -> Dict[str, any]:
        """
        Convenience method to generate speech with the default Piper voice.
        
        Args:
            text: The text to convert to speech
        
        Returns:
            Dictionary with generation results (same as synthesize_speech)
        """
        return cls.synthesize_speech(text=text, voice_id='default', speaker_wav=None)