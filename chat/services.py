"""
Services for speech-to-text transcription, LLM chat completion, text-to-speech, and speech analysis.
"""
import whisper
import requests
import torch
import time
import os
import io
import wave
import re
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from django.conf import settings


def detect_language(text: str) -> str:
    """
    Detect if text is primarily Chinese or English.
    
    Args:
        text: Text to analyze
    
    Returns:
        'zh' for Chinese, 'en' for English
    """
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    
    # If more than 30% of non-space characters are Chinese, consider it Chinese
    total_chars = chinese_chars + english_chars
    if total_chars == 0:
        return 'en'
    
    chinese_ratio = chinese_chars / total_chars
    return 'zh' if chinese_ratio > 0.3 else 'en'


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
                
                model_name = getattr(settings, 'COQUITTS_MODEL_NAME', 'tts_models/multilingual/multi-dataset/xtts_v2')
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
        Auto-detects language (Chinese/English) and selects appropriate language.

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
            
            output_format = getattr(settings, 'COQUITTS_OUTPUT_FORMAT', 'wav')
            
            detected_lang = detect_language(text)
            print(f'Detected language: {detected_lang} for text: "{text[:50]}..."')
            
            if not speaker_wav or not os.path.exists(speaker_wav):
                speaker_wav = getattr(settings, 'COQUITTS_DEFAULT_SPEAKER_WAV', None)
                if not speaker_wav or not os.path.exists(speaker_wav):
                    raise ValueError(
                        "No valid speaker_wav provided and no default speaker found. "
                        "Please upload a voice profile or configure COQUITTS_DEFAULT_SPEAKER_WAV."
                    )
            
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{output_format}') as tmp_file:
                output_path = tmp_file.name
            
            print(f'Generating Coqui TTS for text: "{text[:50]}..." using voice: {speaker_wav} with language: {detected_lang}')
            model.tts_to_file(
                text=text,
                file_path=output_path,
                speaker_wav=speaker_wav,
                language=detected_lang
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
        Auto-detects language (Chinese/English) and selects appropriate model.
        
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
                detected_lang = detect_language(text)
                print(f'Detected language: {detected_lang} for text: "{text[:50]}..."')
                
                piper_models = getattr(settings, 'PIPER_MODELS', {})
                if detected_lang not in piper_models:
                    raise ValueError(
                        f"No Piper model configured for language '{detected_lang}'. "
                        f"Please configure PIPER_{detected_lang.upper()}_MODEL_PATH and "
                        f"PIPER_{detected_lang.upper()}_CONFIG_PATH in your .env file."
                    )
                
                model_config = piper_models[detected_lang]
                model_path = model_config['model_path']
                config_path = model_config['config_path']
                
                if not os.path.exists(model_path):
                    raise FileNotFoundError(
                        f"Piper model file not found for language '{detected_lang}': {model_path}\n"
                        f"Please download the model from https://github.com/rhasspy/piper/releases"
                    )
                
                if not os.path.exists(config_path):
                    raise FileNotFoundError(
                        f"Piper config file not found for language '{detected_lang}': {config_path}"
                    )
                
                print(f'Using {detected_lang} model: {model_path}')
            
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


class SpeechAnalysisService:
    """
    Service for analyzing speech characteristics.
    
    Analyzes three key traits:
    - Confidence: Energy levels, speaking ratio, tempo
    - Stability: Pitch variance, spectral flux, zero-crossing rate stability
    - Warmth: Spectral characteristics, pitch patterns, MFCCs
    """
    
    _vad_model = None
    _vad_utils = None
    
    @classmethod
    def _load_vad_model(cls):
        """Load and cache the Silero VAD model."""
        if cls._vad_model is None:
            try:
                import torch
                torch.set_num_threads(1)
                
                print('Loading Silero VAD model...')
                model, utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=False
                )
                cls._vad_model = model
                cls._vad_utils = utils
                print('Silero VAD model loaded successfully')
            except Exception as e:
                print(f'Error loading Silero VAD model: {e}')
                raise
        
        return cls._vad_model, cls._vad_utils
    
    @classmethod
    def _convert_to_wav(cls, audio_path: str) -> str:
        """
        Convert audio file to WAV format if needed.
        
        Args:
            audio_path: Path to input audio file
        
        Returns:
            Path to WAV file (either original or converted)
        """
        import tempfile
        import subprocess
        
        if audio_path.lower().endswith('.wav'):
            return audio_path
        
        temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_wav_path = temp_wav.name
        temp_wav.close()
        
        try:
            # Use ffmpeg to convert to WAV (16kHz, mono, PCM 16-bit)
            result = subprocess.run([
                'ffmpeg', '-i', audio_path,
                '-ar', '16000',          # Sample rate: 16kHz
                '-ac', '1',              # Channels: Mono
                '-acodec', 'pcm_s16le',  # Codec: PCM 16-bit little-endian
                '-f', 'wav',             # Format: WAV
                '-y',                    # Overwrite without asking
                temp_wav_path
            ], check=True, capture_output=True)
            
            print(f'Audio converted: {audio_path} -> {temp_wav_path}')
            
            return temp_wav_path
        except subprocess.CalledProcessError as e:
            print(f'FFmpeg conversion failed: {e.stderr.decode()}')
            # Cleanup on failure
            if os.path.exists(temp_wav_path):
                os.unlink(temp_wav_path)
            raise
        except FileNotFoundError:
            raise RuntimeError('FFmpeg not found. Please install FFmpeg to enable speech analysis.')
    
    @classmethod
    def _detect_speech_segments(cls, audio_path: str, sample_rate: int = 16000) -> Tuple[List[Dict], float, float]:
        """
        Detect speech segments in audio using Silero VAD.
        
        Args:
            audio_path: Path to audio file (should already be WAV format)
            sample_rate: Target sample rate for VAD (16000 Hz recommended)
        
        Returns:
            Tuple of (segments, total_duration, speech_duration)
            segments: List of {'start': float, 'end': float} in seconds
            total_duration: Total audio duration in seconds
            speech_duration: Total speech duration in seconds
        """
        try:
            model, utils = cls._load_vad_model()
            (get_speech_timestamps, _, read_audio, *_) = utils
            
            # Read audio at 16kHz (VAD requirement)
            # Note: audio_path should already be converted to WAV by caller
            wav = read_audio(audio_path, sampling_rate=sample_rate)
            
            speech_timestamps = get_speech_timestamps(
                wav,
                model,
                sampling_rate=sample_rate,
                threshold=0.5,  # Confidence threshold
                min_speech_duration_ms=250,  # Minimum speech segment
                min_silence_duration_ms=100   # Minimum silence between segments
            )
           
            # Convert timestamps to seconds
            segments = []
            for timestamp in speech_timestamps:
                segments.append({
                    'start': timestamp['start'] / sample_rate,
                    'end': timestamp['end'] / sample_rate
                })
            
            total_duration = len(wav) / sample_rate
            speech_duration = sum(seg['end'] - seg['start'] for seg in segments)
            
            return segments, total_duration, speech_duration
        
        except Exception as e:
            print(f"Error in speech segment detection: {e}")
            raise
    
    @classmethod
    def _extract_features(cls, audio_path: str) -> Dict[str, any]:
        """
        Extract audio features using pyAudioAnalysis.
        
        Args:
            audio_path: Path to audio file
        
        Returns:
            Dictionary with extracted features
        """
        try:
            from pyAudioAnalysis import audioBasicIO
            from pyAudioAnalysis import ShortTermFeatures
            
            print(f'Loading audio file for feature extraction: {audio_path}')
            [Fs, x] = audioBasicIO.read_audio_file(audio_path)
            
            if x is None or len(x) == 0:
                raise ValueError(f'Empty or invalid audio data from file: {audio_path}')
            
            print(f'Audio loaded: sample_rate={Fs}, shape={x.shape}, dtype={x.dtype}')
            
            if x.ndim > 1:
                print(f'Converting stereo to mono (channels: {x.shape[1]})')
                x = np.mean(x, axis=1)
            
            if len(x) == 0:
                raise ValueError('Audio array is empty after mono conversion')
            
            # Extract short-term features (50ms window, 25ms step)
            window_size = int(0.050 * Fs)
            step_size = int(0.025 * Fs)
            
            if window_size == 0 or step_size == 0:
                raise ValueError(f'Invalid window/step size: window={window_size}, step={step_size}')
            
            F, f_names = ShortTermFeatures.feature_extraction(
                x, Fs, window_size, step_size
            )
            
            # F is a 2D array: [feature_index, time_frame]
            # Feature indices (first 13 are most important):
            # 0: ZCR (Zero Crossing Rate)
            # 1: Energy
            # 2: Energy Entropy
            # 3: Spectral Centroid
            # 4: Spectral Spread
            # 5: Spectral Entropy
            # 6: Spectral Flux
            # 7: Spectral Rolloff
            # 8-12: MFCCs 1-5
            # 13+: Additional MFCCs
            
            features = {
                'zcr_mean': float(np.mean(F[0, :])),
                'zcr_std': float(np.std(F[0, :])),
                'energy_mean': float(np.mean(F[1, :])),
                'energy_std': float(np.std(F[1, :])),
                'energy_entropy_mean': float(np.mean(F[2, :])),
                'spectral_centroid_mean': float(np.mean(F[3, :])),
                'spectral_centroid_std': float(np.std(F[3, :])),
                'spectral_spread_mean': float(np.mean(F[4, :])),
                'spectral_entropy_mean': float(np.mean(F[5, :])),
                'spectral_flux_mean': float(np.mean(F[6, :])),
                'spectral_rolloff_mean': float(np.mean(F[7, :])),
                'mfcc_1_mean': float(np.mean(F[8, :])),
                'mfcc_2_mean': float(np.mean(F[9, :])),
                'mfcc_3_mean': float(np.mean(F[10, :])),
            }
            
            return features
        
        except Exception as e:
            print(f"Error extracting features: {e}")
            raise
    
    @classmethod
    def _calculate_confidence(cls, features: Dict, speaking_ratio: float) -> float:
        """
        Calculate confidence score (0-100) based on:
        - Energy levels (higher = more confident)
        - Speaking ratio (higher = more confident)
        - Energy stability (consistent high energy = confident)
        
        Args:
            features: Extracted audio features
            speaking_ratio: Ratio of speech time to total time (0-1)
        
        Returns:
            Confidence score (0-100)
        """
        # Energy score: normalize mean energy (typical range 0-1)
        energy_score = min(features['energy_mean'] / 0.5, 1.0)
        
        # Speaking ratio score (penalize too much silence)
        speaking_ratio_score = speaking_ratio
        
        # Energy stability score (low variance = confident)
        # Typical energy_std is 0-0.3, so normalize
        energy_stability = 1 - min(features['energy_std'] / 0.3, 1.0)
        
        # Spectral rolloff can indicate vocal projection
        # Higher rolloff = more high-frequency energy = confident voice
        # Typical range: 2000-6000 Hz
        rolloff_score = min(features['spectral_rolloff_mean'] / 6000, 1.0)
        
        # Weighted combination
        confidence = (
            0.30 * energy_score +
            0.25 * speaking_ratio_score +
            0.25 * energy_stability +
            0.20 * rolloff_score
        ) * 100
        
        return max(0, min(100, confidence))
    
    @classmethod
    def _calculate_stability(cls, features: Dict) -> float:
        """
        Calculate stability score (0-100) based on:
        - Low pitch variance (estimated from spectral features)
        - Low spectral flux (minimal spectral changes)
        - Low ZCR variance (consistent voice quality)
        
        Args:
            features: Extracted audio features
        
        Returns:
            Stability score (0-100)
        """
        # Spectral centroid stability (low std = stable)
        # Typical std: 100-500 Hz
        spectral_stability = 1 - min(features['spectral_centroid_std'] / 500, 1.0)
        
        # Spectral flux (low = stable, typical range 0-0.5)
        flux_stability = 1 - min(features['spectral_flux_mean'] / 0.5, 1.0)
        
        # ZCR stability (low variance = stable)
        # Typical ZCR std: 0-0.1
        zcr_stability = 1 - min(features['zcr_std'] / 0.1, 1.0)
        
        # Energy entropy (lower = more stable energy distribution)
        # Typical range: 0-3
        energy_entropy_stability = 1 - min(features['energy_entropy_mean'] / 3.0, 1.0)
        
        # Weighted combination
        stability = (
            0.35 * spectral_stability +
            0.30 * flux_stability +
            0.20 * zcr_stability +
            0.15 * energy_entropy_stability
        ) * 100
        
        return max(0, min(100, stability))
    
    @classmethod
    def _calculate_warmth(cls, features: Dict) -> float:
        """
        Calculate warmth/affability score (0-100) based on:
        - Lower spectral centroid (warmer tone)
        - Moderate spectral spread (not too narrow or wide)
        - MFCC patterns associated with friendly speech
        
        Args:
            features: Extracted audio features
        
        Returns:
            Warmth score (0-100)
        """
        # Spectral centroid warmth (lower = warmer, typical: 1000-4000 Hz)
        # Warmest voices around 1500-2500 Hz
        centroid = features['spectral_centroid_mean']
        if 1500 <= centroid <= 2500:
            warmth_centroid = 1.0
        elif centroid < 1500:
            warmth_centroid = centroid / 1500
        else:
            warmth_centroid = max(0, 1 - (centroid - 2500) / 2500)
        
        # Spectral spread (moderate is better, typical: 200-800 Hz)
        spread = features['spectral_spread_mean']
        warmth_spread = 1 - abs(spread - 500) / 500
        warmth_spread = max(0, min(1, warmth_spread))
        
        # Spectral entropy (moderate = expressive, typical: 0.5-2.5)
        entropy = features['spectral_entropy_mean']
        warmth_entropy = 1 - abs(entropy - 1.5) / 1.5
        warmth_entropy = max(0, min(1, warmth_entropy))
        
        # MFCCs (certain patterns indicate warmth)
        # MFCC 1 relates to energy distribution
        # MFCC 2-3 relate to spectral shape
        # For warmth, we want moderate values
        mfcc_score = min(abs(features['mfcc_1_mean']) / 50, 1.0)
        
        # Weighted combination
        warmth = (
            0.40 * warmth_centroid +
            0.25 * warmth_spread +
            0.20 * warmth_entropy +
            0.15 * mfcc_score
        ) * 100
        
        return max(0, min(100, warmth))
    
    @classmethod
    def analyze(cls, audio_file_path: str) -> Dict[str, any]:
        """
        Analyze speech characteristics from an audio file.
        
        Args:
            audio_file_path: Absolute path to the audio file
        
        Returns:
            Dictionary with analysis results:
            {
                'confidence': float (0-100),
                'stability': float (0-100),
                'warmth': float (0-100),
                'details': {
                    'speaking_ratio': float (0-1),
                    'total_duration': float (seconds),
                    'speech_duration': float (seconds),
                    'mean_energy': float,
                    'spectral_centroid': float,
                    'spectral_flux': float,
                    ...
                },
                'analyzed_at': str (ISO timestamp)
            }
        """
        converted_path = None
        try:
            print(f'Starting speech analysis for: {audio_file_path}')
            start_time = time.time()
            
            # Convert to WAV once (if needed) and reuse for both operations
            converted_path = cls._convert_to_wav(audio_file_path)
            print(f'Using audio file: {converted_path}')
            
            # Step 1: Detect speech segments using Silero VAD
            segments, total_duration, speech_duration = cls._detect_speech_segments(converted_path)
            speaking_ratio = speech_duration / total_duration if total_duration > 0 else 0
            
            print(f'VAD complete: {len(segments)} segments, '
                  f'speaking ratio: {speaking_ratio:.2f}')
            
            # Step 2: Extract audio features using pyAudioAnalysis
            features = cls._extract_features(converted_path)
            print(f'Feature extraction complete')
            
            confidence = cls._calculate_confidence(features, speaking_ratio)
            stability = cls._calculate_stability(features)
            warmth = cls._calculate_warmth(features)
            
            analysis_time = time.time() - start_time
            
            print(f'Speech analysis complete in {analysis_time:.2f}s - '
                  f'Confidence: {confidence:.1f}, '
                  f'Stability: {stability:.1f}, '
                  f'Warmth: {warmth:.1f}')
            
            return {
                'confidence': round(confidence, 2),
                'stability': round(stability, 2),
                'warmth': round(warmth, 2),
                'details': {
                    'speaking_ratio': round(speaking_ratio, 3),
                    'total_duration': round(total_duration, 2),
                    'speech_duration': round(speech_duration, 2),
                    'num_segments': len(segments),
                    'mean_energy': round(features['energy_mean'], 4),
                    'energy_std': round(features['energy_std'], 4),
                    'spectral_centroid': round(features['spectral_centroid_mean'], 2),
                    'spectral_flux': round(features['spectral_flux_mean'], 4),
                    'zcr_std': round(features['zcr_std'], 4),
                    'analysis_time': round(analysis_time, 2)
                },
                'analyzed_at': datetime.utcnow().isoformat() + 'Z'
            }
        
        except Exception as e:
            print(f'Error in speech analysis: {e}')
            import traceback
            traceback.print_exc()
            raise
        finally:
            # Cleanup: Delete temporary converted file if it's not the original
            if converted_path and converted_path != audio_file_path:
                try:
                    if os.path.exists(converted_path):
                        os.unlink(converted_path)
                        print(f'Cleaned up temporary file: {converted_path}')
                except Exception as e:
                    print(f'Warning: Failed to cleanup temp file {converted_path}: {e}')