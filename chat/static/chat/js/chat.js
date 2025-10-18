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

        this.initializeEventListeners();
        this.checkMicrophoneSupport();
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

    handleAudioRecorded(audioBlob) {
        // Create a URL for the audio blob
        const audioUrl = URL.createObjectURL(audioBlob);

        // For now, just show a message that audio was recorded
        // In a real implementation, you would send this to a speech-to-text API
        this.addMessage('user', `[Voice message recorded - ${(audioBlob.size / 1024).toFixed(1)} KB]`);

        // TODO: Send audioBlob to backend for speech-to-text conversion
        console.log('Audio recorded:', audioBlob);

        // Simulate AI response
        setTimeout(() => {
            this.addMessage('assistant', 'Voice message received! Speech-to-text integration coming soon.');
        }, 1000);
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

        console.log('New chat created');
    }
}

// Initialize the chat application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const chat = new VoiceChat();
});
