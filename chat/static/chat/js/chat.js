// Chat Application with Voice Recording
class VoiceChat {
    constructor() {
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.voiceBtn = document.getElementById('voiceBtn');
        this.messagesContainer = document.getElementById('messagesContainer');
        this.newChatBtn = document.getElementById('newChatBtn');
        this.recordingIndicator = document.getElementById('recordingIndicator');
        this.recordingTime = document.getElementById('recordingTime');
        this.stopRecordingBtn = document.getElementById('stopRecordingBtn');

        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.recordingStartTime = null;
        this.recordingInterval = null;
        this.sessionId = null;  // Track current chat session

        this.initializeEventListeners();
        this.checkMicrophoneSupport();
    }

    // Get CSRF token from cookie
    getCsrfToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    initializeEventListeners() {
        // Send button click
        this.sendBtn.addEventListener('click', () => this.sendMessage());

        // Enter key to send (Shift+Enter for new line)
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = this.messageInput.scrollHeight + 'px';
        });

        // Voice recording
        this.voiceBtn.addEventListener('click', () => this.toggleRecording());
        this.stopRecordingBtn.addEventListener('click', () => this.stopRecording());

        // New chat button
        this.newChatBtn.addEventListener('click', () => this.createNewChat());
    }

    checkMicrophoneSupport() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.voiceBtn.disabled = true;
            this.voiceBtn.title = 'Voice recording not supported in this browser';
            console.warn('Media devices not supported');
        }
    }

    async toggleRecording() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(stream);
            this.audioChunks = [];

            this.mediaRecorder.addEventListener('dataavailable', (event) => {
                this.audioChunks.push(event.data);
            });

            this.mediaRecorder.addEventListener('stop', () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                this.handleAudioRecorded(audioBlob);
                stream.getTracks().forEach(track => track.stop());
            });

            this.mediaRecorder.start();
            this.isRecording = true;
            this.voiceBtn.classList.add('recording');
            this.recordingIndicator.style.display = 'flex';

            // Start recording timer
            this.recordingStartTime = Date.now();
            this.updateRecordingTime();
            this.recordingInterval = setInterval(() => this.updateRecordingTime(), 1000);

        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Could not access microphone. Please check your browser permissions.');
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.voiceBtn.classList.remove('recording');
            this.recordingIndicator.style.display = 'none';

            if (this.recordingInterval) {
                clearInterval(this.recordingInterval);
                this.recordingInterval = null;
            }
        }
    }

    updateRecordingTime() {
        if (!this.recordingStartTime) return;

        const elapsed = Math.floor((Date.now() - this.recordingStartTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        this.recordingTime.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }

    async handleAudioRecorded(audioBlob) {
        // Show loading indicator
        const loadingId = this.addMessage('assistant', '🎤 Transcribing your message...');

        try {
            const formData = new FormData();
            formData.append('recording', audioBlob, `recording_${Date.now()}.webm`);

            // Include session_id if we have one
            if (this.sessionId) {
                formData.append('session_id', this.sessionId);
            }

            const response = await fetch('/api/chat/upload-recording/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrfToken(),
                },
                body: formData,
            });

            const result = await response.json();

            // Remove loading indicator
            this.removeMessage(loadingId);

            if (result.success && result.user_message && result.assistant_message) {
                // Store the session_id for future requests
                if (result.session_id) {
                    this.sessionId = result.session_id;
                }

                // Display transcribed user message
                this.addMessage('user', result.user_message.content);

                // Display AI response
                this.addMessage('assistant', result.assistant_message.content);

                console.log('Voice message processed:', {
                    transcription: result.transcription,
                    session_id: result.session_id
                });
            } else {
                console.error('Processing failed:', result.message);
                this.addMessage('assistant', `Error: ${result.message}`);
            }
        } catch (error) {
            console.error('Error processing voice message:', error);
            this.removeMessage(loadingId);
            this.addMessage('assistant', 'Failed to process voice message. Please try again.');
        }
    }

    sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        // Add user message
        this.addMessage('user', message);

        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';

        // Simulate AI response (replace with actual API call)
        setTimeout(() => {
            this.addMessage('assistant', 'This is a demo response. AI integration coming soon!');
        }, 1000);
    }

    addMessage(role, content) {
        // Remove welcome message if it exists
        const welcomeMessage = this.messagesContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }

        const messageDiv = document.createElement('div');
        const messageId = `msg-${Date.now()}-${Math.random()}`;
        messageDiv.id = messageId;
        messageDiv.className = `message ${role}`;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.textContent = role === 'user' ? 'U' : 'AI';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        const wrapper = document.createElement('div');
        wrapper.appendChild(contentDiv);
        wrapper.appendChild(timeDiv);

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(wrapper);

        this.messagesContainer.appendChild(messageDiv);

        // Scroll to bottom
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;

        return messageId;
    }

    removeMessage(messageId) {
        const messageElement = document.getElementById(messageId);
        if (messageElement) {
            messageElement.remove();
        }
    }

    createNewChat() {
        // Clear messages
        this.messagesContainer.innerHTML = `
            <div class="welcome-message">
                <h2>Welcome to Voice Chat!</h2>
                <p>Type a message or click the microphone button to record your voice.</p>
            </div>
        `;

        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';

        // Clear session ID to start a new conversation
        this.sessionId = null;

        console.log('New chat created');
    }
}

// Initialize the chat application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const chat = new VoiceChat();
});
