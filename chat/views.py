import uuid
from django.shortcuts import render
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import MultiPartParser, FormParser
from .models import ChatSession, ChatMessage, AudioFile, VoiceProfile, TTSAudioFile
from .services import WhisperService, LocalLLMService, CloneTTSService, PiperTTSService, SpeechAnalysisService
from .serializers import (
    VoiceRecordingRequestSerializer,
    VoiceRecordingResponseSerializer,
    ChatMessageSerializer,
    SendMessageRequestSerializer,
    SendMessageResponseSerializer,
    VoiceProfileSerializer,
    VoiceProfileUploadSerializer
)


def chat_interface(request):
    """Render the main chat interface."""
    return render(request, 'chat/chat_interface.html')


class UploadRecordingView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    
    @extend_schema(
        summary="Upload and transcribe a voice recording",
        description="Upload a voice recording, transcribe it, and create a user message. Returns transcription only - use /send-message/ to get AI response.",
        request=VoiceRecordingRequestSerializer,
        responses={
            201: VoiceRecordingResponseSerializer,
        },
    )
    def post(self, request):
        input_serializer = VoiceRecordingRequestSerializer(data=request.data)
        
        if input_serializer.is_valid():
            try:
                user = request.user if request.user.is_authenticated else type('obj', (object,), {'id': 'anonymous'})()
                
                audio_file = input_serializer.save(user=user)
                
                audio_file.transcription_status = AudioFile.TRANSCRIBING
                audio_file.save()
                
                audio_file_path = audio_file.file.path
                transcription_result = WhisperService.transcribe(audio_file_path)
                transcription_text = transcription_result['text']
                
                if not transcription_text:
                    audio_file.transcription_status = AudioFile.FAILED
                    audio_file.save()
                    
                    return Response({
                        'success': False,
                        'message': 'Could not transcribe audio',
                        'audio_file': {'id': audio_file.id, 'status': audio_file.transcription_status}
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                audio_file.transcription_status = AudioFile.COMPLETED
                audio_file.transcription_text = transcription_text
                audio_file.save()
                
                try:
                    audio_file.analysis_status = 'analyzing'
                    audio_file.save()
                    
                    analysis_result = SpeechAnalysisService.analyze(audio_file_path)
                    
                    audio_file.speech_analysis = analysis_result
                    audio_file.analysis_status = AudioFile.COMPLETED
                    audio_file.save()
                    
                except Exception as e:
                    print(f'Speech analysis failed: {str(e)}')
                    import traceback
                    traceback.print_exc()
                    audio_file.analysis_status = AudioFile.FAILED
                    audio_file.analysis_error = str(e)
                    audio_file.save()
                    # Don't fail the entire request - transcription succeeded
                
                session_id = input_serializer.validated_data.get('session_id')
                if session_id:
                    session, _ = ChatSession.objects.get_or_create(
                        session_id=session_id,
                        defaults={'user': request.user if request.user.is_authenticated else None}
                    )
                else:
                    session_id = str(uuid.uuid4())
                    session = ChatSession.objects.create(
                        session_id=session_id,
                        user=request.user if request.user.is_authenticated else None
                    )
                
                user_message = ChatMessage.objects.create(
                    role=ChatMessage.USER,
                    content=transcription_text,
                    session=session,
                    user=request.user if request.user.is_authenticated else None,
                    audio_file=audio_file
                )
                
                session.update_activity()
                
                user_msg_serializer = ChatMessageSerializer(user_message)
                
                response_data = {
                    'success': True,
                    'message': 'Audio transcribed successfully',
                    'transcription': transcription_text,
                    'session_id': session_id,
                    'user_message': user_msg_serializer.data,
                }
                
                if audio_file.analysis_status == AudioFile.COMPLETED and audio_file.speech_analysis:
                    response_data['speech_analysis'] = audio_file.speech_analysis
                
                return Response(response_data, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                import traceback
                traceback.print_exc()
                return Response({
                    'success': False,
                    'message': 'Error processing voice recording',
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': input_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class SendMessageView(APIView):
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Send a message and get AI response",
        description="Send a text message or reference an existing voice message to get an AI response. Supports conversation history.",
        request=SendMessageRequestSerializer,
        responses={
            200: SendMessageResponseSerializer,
        },
    )
    def post(self, request):
        input_serializer = SendMessageRequestSerializer(data=request.data)
        
        if input_serializer.is_valid():
            try:
                session_id = input_serializer.validated_data['session_id']
                message_id = input_serializer.validated_data.get('message_id')
                content = input_serializer.validated_data.get('content')
                speed_mode = input_serializer.validated_data.get('speed_mode', 'fast')
                
                try:
                    session = ChatSession.objects.get(session_id=session_id)
                except ChatSession.DoesNotExist:
                    if content:
                        session = ChatSession.objects.create(
                            session_id=session_id,
                            user=request.user if request.user.is_authenticated else None
                        )
                    else:
                        return Response({
                            'success': False,
                            'message': f'Session {session_id} not found'
                        }, status=status.HTTP_404_NOT_FOUND)
                
                user_message = None
                
                if message_id:
                    try:
                        user_message = ChatMessage.objects.get(
                            id=message_id,
                            session=session,
                            role=ChatMessage.USER
                        )
                        content = user_message.content
                    except ChatMessage.DoesNotExist:
                        return Response({
                            'success': False,
                            'message': f'Message {message_id} not found in session {session_id}'
                        }, status=status.HTTP_404_NOT_FOUND)
                
                elif content:
                    user_message = ChatMessage.objects.create(
                        role=ChatMessage.USER,
                        content=content,
                        session=session,
                        user=request.user if request.user.is_authenticated else None
                    )
                
                previous_messages = ChatMessage.objects.filter(
                    session=session
                ).order_by('timestamp')
                
                if user_message and not message_id:
                    previous_messages = previous_messages.exclude(id=user_message.id)
                
                previous_messages = previous_messages[:10]
                
                conversation_history = [
                    {'role': msg.role, 'content': msg.content}
                    for msg in previous_messages
                ]
                
                llm_response = LocalLLMService.generate_response(
                    prompt=content,
                    conversation_history=conversation_history
                )
                
                assistant_message = ChatMessage.objects.create(
                    role=ChatMessage.ASSISTANT,
                    content=llm_response,
                    session=session,
                    model=settings.LOCAL_LLM_MODEL
                )
                
                try:
                    voice_profile = None
                    if request.user.is_authenticated:
                        voice_profile = VoiceProfile.objects.filter(
                            user=request.user,
                            is_default=True
                        ).first()
                    
                    if not voice_profile:
                        voice_profile = VoiceProfile.objects.filter(
                            user=None,
                            is_default=True
                        ).first()
                    
                    if speed_mode == 'fast':
                        speaker_wav = None
                        if voice_profile and voice_profile.piper_model_file:
                            speaker_wav = voice_profile.piper_model_file.path
                        
                        tts_result = PiperTTSService.synthesize_speech(
                            text=llm_response,
                            voice_id=voice_profile.voice_id if voice_profile else 'default',
                            speaker_wav=speaker_wav
                        )
                    else:
                        speaker_wav = None
                        if voice_profile and voice_profile.reference_audio:
                            speaker_wav = voice_profile.reference_audio.path
                        
                        tts_result = CloneTTSService.synthesize_speech(
                            text=llm_response,
                            voice_id=voice_profile.voice_id if voice_profile else 'default',
                            speaker_wav=speaker_wav
                        )
                    
                    from django.core.files.base import ContentFile
                    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                    filename = f'tts_{assistant_message.id}_{timestamp}.wav'
                    
                    tts_audio = TTSAudioFile(
                        message=assistant_message,
                        voice_profile=voice_profile,
                        file_size=tts_result['file_size'],
                        mime_type=tts_result['mime_type'],
                        generation_time=tts_result['generation_time']
                    )
                    tts_audio.file.save(filename, ContentFile(tts_result['audio_bytes']), save=True)
                    
                    print(f'TTS audio generated and saved for message {assistant_message.id}')
                
                except Exception as e:
                    import traceback
                    print(f'Warning: TTS generation failed for message {assistant_message.id}: {e}')
                    traceback.print_exc()
                
                session.update_activity()
                
                assistant_msg_serializer = ChatMessageSerializer(assistant_message)
                
                return Response({
                    'success': True,
                    'message': 'AI response generated successfully',
                    'session_id': session_id,
                    'assistant_message': assistant_msg_serializer.data,
                    'speed_mode': speed_mode,
                }, status=status.HTTP_200_OK)
            
            except Exception as e:
                import traceback
                traceback.print_exc()
                return Response({
                    'success': False,
                    'message': 'Error generating AI response',
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': input_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class VoiceProfileUploadView(APIView):
    """API view for uploading custom voice profiles."""
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    
    @extend_schema(
        summary="Upload a custom voice profile",
        description="Upload a reference audio file to create a custom voice profile for TTS. The audio should be 6-30 seconds of clean speech.",
        request=VoiceProfileUploadSerializer,
        responses={
            201: VoiceProfileSerializer,
        },
    )
    def post(self, request):
        input_serializer = VoiceProfileUploadSerializer(data=request.data)
        
        if input_serializer.is_valid():
            try:
                user = request.user if request.user.is_authenticated else type('obj', (object,), {'id': 'anonymous'})()
                
                voice_profile = input_serializer.save(user=user)
                
                output_serializer = VoiceProfileSerializer(voice_profile)
                
                return Response({
                    'success': True,
                    'message': 'Voice profile created successfully',
                    'voice_profile': output_serializer.data,
                }, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                import traceback
                traceback.print_exc()
                return Response({
                    'success': False,
                    'message': 'Error creating voice profile',
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': input_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class VoiceProfileListView(APIView):
    """API view for listing available voice profiles."""
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="List available voice profiles",
        description="Get a list of available voice profiles (system default + user's custom voices).",
        responses={
            200: VoiceProfileSerializer(many=True),
        },
    )
    def get(self, request):
        try:
            # Get system default voices and user's custom voices
            profiles = VoiceProfile.objects.filter(
                user=None  # System default
            )
            
            if request.user.is_authenticated:
                # Include user's custom voices
                user_profiles = VoiceProfile.objects.filter(user=request.user)
                profiles = profiles | user_profiles
            
            serializer = VoiceProfileSerializer(profiles, many=True)
            
            return Response({
                'success': True,
                'count': profiles.count(),
                'voice_profiles': serializer.data,
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'success': False,
                'message': 'Error retrieving voice profiles',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)