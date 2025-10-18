import uuid
from django.shortcuts import render
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import MultiPartParser, FormParser
from .models import ChatSession, ChatMessage, AudioFile
from .services import WhisperService, LocalLLMService
from .serializers import (
    VoiceRecordingRequestSerializer,
    VoiceRecordingResponseSerializer,
    ChatMessageSerializer,
    SendMessageRequestSerializer,
    SendMessageResponseSerializer
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
                
                return Response({
                    'success': True,
                    'message': 'Audio transcribed successfully',
                    'transcription': transcription_text,
                    'session_id': session_id,
                    'user_message': user_msg_serializer.data,
                }, status=status.HTTP_201_CREATED)
            
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
                
                session.update_activity()
                
                assistant_msg_serializer = ChatMessageSerializer(assistant_message)
                
                return Response({
                    'success': True,
                    'message': 'AI response generated successfully',
                    'session_id': session_id,
                    'assistant_message': assistant_msg_serializer.data,
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