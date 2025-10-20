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

        // Voice settings
        this.voiceSettingsBtn = document.getElementById('voiceSettingsBtn');
        this.voiceSettingsModal = document.getElementById('voiceSettingsModal');
        this.closeModalBtn = document.getElementById('closeModalBtn');
        this.voiceUploadForm = document.getElementById('voiceUploadForm');
        this.voiceProfilesList = document.getElementById('voiceProfilesList');

        // Speed mode toggle
        this.speedModeToggle = document.getElementById('speedModeToggle');
        this.fastModeBtn = document.getElementById('fastModeBtn');
        this.qualityModeBtn = document.getElementById('qualityModeBtn');

        // Voice profile recording
        this.recordTab = document.getElementById('recordTab');
        this.uploadTab = document.getElementById('uploadTab');
        this.recordContent = document.getElementById('recordContent');
        this.uploadContent = document.getElementById('uploadContent');
        this.startVoiceRecordBtn = document.getElementById('startVoiceRecordBtn');
        this.stopVoiceRecordBtn = document.getElementById('stopVoiceRecordBtn');
        this.voiceRecordForm = document.getElementById('voiceRecordForm');
        this.cancelRecordBtn = document.getElementById('cancelRecordBtn');
        this.voicePreview = document.getElementById('voicePreview');
        this.voiceRecordTimer = document.getElementById('voiceRecordTimer');
        this.voiceRecordTime = document.getElementById('voiceRecordTime');
        this.recorderStatus = document.getElementById('recorderStatus');

        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.recordingStartTime = null;
        this.recordingInterval = null;
        this.sessionId = null;  // Track current chat session
        this.speedMode = 'fast';  // Track TTS speed mode (fast/quality)
        this.voiceProfileCount = 0;  // Track number of voice profiles

        // Voice profile recording state
        this.isVoiceProfileRecording = false;
        this.voiceProfileMediaRecorder = null;
        this.voiceProfileAudioChunks = [];
        this.voiceProfileRecordingStartTime = null;
        this.voiceProfileRecordingInterval = null;
        this.recordedVoiceBlob = null;

        this.initializeEventListeners();
        this.checkMicrophoneSupport();
        this.checkVoiceProfiles();  // Check voice profiles on load
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

        // Voice settings
        this.voiceSettingsBtn.addEventListener('click', () => this.openVoiceSettings());
        this.closeModalBtn.addEventListener('click', () => this.closeVoiceSettings());
        this.voiceUploadForm.addEventListener('submit', (e) => this.uploadVoiceProfile(e));

        // Speed mode toggle
        this.fastModeBtn.addEventListener('click', () => this.setSpeedMode('fast'));
        this.qualityModeBtn.addEventListener('click', () => this.setSpeedMode('quality'));

        // Voice profile tabs
        this.recordTab.addEventListener('click', () => this.switchTab('record'));
        this.uploadTab.addEventListener('click', () => this.switchTab('upload'));

        // Voice profile recording
        this.startVoiceRecordBtn.addEventListener('click', () => this.startVoiceProfileRecording());
        this.stopVoiceRecordBtn.addEventListener('click', () => this.stopVoiceProfileRecording());
        this.voiceRecordForm.addEventListener('submit', (e) => this.saveRecordedVoiceProfile(e));
        this.cancelRecordBtn.addEventListener('click', () => this.cancelVoiceRecording());

        // Close modal on outside click
        this.voiceSettingsModal.addEventListener('click', (e) => {
            if (e.target === this.voiceSettingsModal) {
                this.closeVoiceSettings();
            }
        });
    }

    checkMicrophoneSupport() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.voiceBtn.disabled = true;
            this.voiceBtn.title = 'Voice recording not supported in this browser';
            console.warn('Media devices not supported');
        }
    }

    async checkVoiceProfiles() {
        try {
            const response = await fetch('/api/chat/voice-profiles/', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.voiceProfileCount = data.count || 0;
                this.updateQualityModeState();
            }
        } catch (error) {
            console.error('Error checking voice profiles:', error);
        }
    }

    updateQualityModeState() {
        if (this.voiceProfileCount === 0) {
            // Disable quality mode button if no profiles
            this.qualityModeBtn.disabled = true;
            this.qualityModeBtn.title = 'Create a voice profile to use Quality mode';
            this.qualityModeBtn.style.opacity = '0.5';
            this.qualityModeBtn.style.cursor = 'not-allowed';

            // If currently in quality mode, switch to fast mode
            if (this.speedMode === 'quality') {
                this.setSpeedMode('fast');
            }
        } else {
            // Enable quality mode button
            this.qualityModeBtn.disabled = false;
            this.qualityModeBtn.title = 'Quality mode with voice cloning (15-30s, XTTS v2)';
            this.qualityModeBtn.style.opacity = '1';
            this.qualityModeBtn.style.cursor = 'pointer';
        }
    }

    setSpeedMode(mode) {
        this.speedMode = mode;

        // Update button states
        if (mode === 'fast') {
            this.fastModeBtn.classList.add('active');
            this.qualityModeBtn.classList.remove('active');
            console.log('TTS speed mode set to: Fast (<1s, Piper TTS)');
        } else {
            this.fastModeBtn.classList.remove('active');
            this.qualityModeBtn.classList.add('active');
            console.log('TTS speed mode set to: Quality (15-30s, XTTS v2 with voice cloning)');
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
        // Phase 1: Transcription
        const transcribingId = this.addMessage('assistant', '🎤 Transcribing...');

        try {
            // Step 1: Upload and transcribe
            const formData = new FormData();
            formData.append('recording', audioBlob, `recording_${Date.now()}.webm`);

            // Include session_id if we have one
            if (this.sessionId) {
                formData.append('session_id', this.sessionId);
            }

            const uploadResponse = await fetch('/api/chat/upload-recording/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrfToken(),
                },
                body: formData,
            });

            const uploadResult = await uploadResponse.json();

            // Remove transcribing indicator
            this.removeMessage(transcribingId);

            if (!uploadResult.success) {
                console.error('Upload/transcription failed:', uploadResult.message);
                this.addMessage('assistant', `Error: ${uploadResult.message}`);
                return;
            }

            // Store session_id
            if (uploadResult.session_id) {
                this.sessionId = uploadResult.session_id;
            }

            // Display transcribed user message with speech analysis
            this.addMessage('user', uploadResult.user_message.content, null, uploadResult.speech_analysis);

            console.log('Transcription completed:', {
                transcription: uploadResult.transcription,
                session_id: uploadResult.session_id,
                speech_analysis: uploadResult.speech_analysis
            });

            // Phase 2: AI Response
            // Validate: Quality mode requires a voice profile
            if (this.speedMode === 'quality' && this.voiceProfileCount === 0) {
                this.addMessage('assistant', 'Quality mode requires a voice profile. Please create a voice profile or switch to Fast mode.');
                return;
            }

            const thinkingId = this.addMessage('assistant', '💭 AI is thinking...');

            try {
                // Step 2: Get AI response
                const aiResponse = await fetch('/api/chat/send-message/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': this.getCsrfToken()
                    },
                    body: JSON.stringify({
                        session_id: this.sessionId,
                        message_id: uploadResult.user_message.id,
                        speed_mode: this.speedMode
                    })
                });

                const aiResult = await aiResponse.json();

                // Remove thinking indicator
                this.removeMessage(thinkingId);

                if (aiResult.success) {
                    // Display AI response with TTS audio if available
                    this.addMessage('assistant', aiResult.assistant_message.content, aiResult.assistant_message.tts_audio);
                    console.log('AI response received');
                } else {
                    // Handle specific error codes
                    if (aiResult.error_code === 'VOICE_PROFILE_REQUIRED') {
                        // Show text response even if TTS failed
                        if (aiResult.assistant_message) {
                            this.addMessage('assistant', aiResult.assistant_message.content);
                        }
                        // Show error modal with options
                        alert(`${aiResult.message}\n\nYou can:\n1. Create a voice profile in "Manage Voices"\n2. Switch to Fast mode`);
                    } else {
                        console.error('AI response failed:', aiResult.message);
                        this.addMessage('assistant', `Error: ${aiResult.message}`);
                    }
                }

            } catch (error) {
                console.error('Error getting AI response:', error);
                this.removeMessage(thinkingId);
                this.addMessage('assistant', 'Failed to get AI response. Please try again.');
            }

        } catch (error) {
            console.error('Error processing voice message:', error);
            this.removeMessage(transcribingId);
            this.addMessage('assistant', 'Failed to process voice message. Please try again.');
        }
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        // Validate: Quality mode requires a voice profile
        if (this.speedMode === 'quality' && this.voiceProfileCount === 0) {
            alert('Quality mode requires a voice profile. Please create a voice profile or switch to Fast mode.');
            return;
        }

        // Add user message
        this.addMessage('user', message);

        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';

        // Show AI thinking indicator
        const thinkingId = this.addMessage('assistant', '💭 AI is thinking...');

        try {
            // Generate session_id if we don't have one
            if (!this.sessionId) {
                this.sessionId = this.generateSessionId();
            }

            // Call send-message API
            const response = await fetch('/api/chat/send-message/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    content: message,
                    speed_mode: this.speedMode
                })
            });

            const result = await response.json();

            // Remove thinking indicator
            this.removeMessage(thinkingId);

            if (result.success) {
                // Update session_id if it was created on the backend
                if (result.session_id) {
                    this.sessionId = result.session_id;
                }

                // Display AI response with TTS audio if available
                this.addMessage('assistant', result.assistant_message.content, result.assistant_message.tts_audio);
                console.log('AI response received for text message');
            } else {
                // Handle specific error codes
                if (result.error_code === 'VOICE_PROFILE_REQUIRED') {
                    // Show text response even if TTS failed
                    if (result.assistant_message) {
                        this.addMessage('assistant', result.assistant_message.content);
                    }
                    // Show error modal with options
                    alert(`${result.message}\n\nYou can:\n1. Create a voice profile in "Manage Voices"\n2. Switch to Fast mode`);
                } else {
                    console.error('AI response failed:', result.message);
                    this.addMessage('assistant', `Error: ${result.message}`);
                }
            }

        } catch (error) {
            console.error('Error sending message:', error);
            this.removeMessage(thinkingId);
            this.addMessage('assistant', 'Failed to send message. Please try again.');
        }
    }

    generateSessionId() {
        // Generate a simple UUID v4
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    addMessage(role, content, ttsAudio = null, speechAnalysis = null) {
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

        // Add speech analysis scores if available (for user voice messages)
        if (role === 'user' && speechAnalysis) {
            const analysisContainer = document.createElement('div');
            analysisContainer.className = 'speech-analysis-container';

            const analysisTitle = document.createElement('div');
            analysisTitle.className = 'analysis-title';
            analysisTitle.textContent = '🎯 Speech Analysis';

            const scoresContainer = document.createElement('div');
            scoresContainer.className = 'analysis-scores';

            // Create score bars for confidence, stability, warmth
            const scores = [
                { label: 'Confidence', value: speechAnalysis.confidence, color: '#4CAF50' },
                { label: 'Stability', value: speechAnalysis.stability, color: '#2196F3' },
                { label: 'Warmth', value: speechAnalysis.warmth, color: '#FF9800' }
            ];

            scores.forEach(score => {
                const scoreItem = document.createElement('div');
                scoreItem.className = 'score-item';

                const scoreLabel = document.createElement('span');
                scoreLabel.className = 'score-label';
                scoreLabel.textContent = score.label;

                const scoreBarContainer = document.createElement('div');
                scoreBarContainer.className = 'score-bar-container';

                const scoreBar = document.createElement('div');
                scoreBar.className = 'score-bar';
                scoreBar.style.width = `${score.value}%`;
                scoreBar.style.backgroundColor = score.color;

                const scoreValue = document.createElement('span');
                scoreValue.className = 'score-value';
                scoreValue.textContent = score.value.toFixed(1);

                scoreBarContainer.appendChild(scoreBar);
                scoreItem.appendChild(scoreLabel);
                scoreItem.appendChild(scoreBarContainer);
                scoreItem.appendChild(scoreValue);
                scoresContainer.appendChild(scoreItem);
            });

            analysisContainer.appendChild(analysisTitle);
            analysisContainer.appendChild(scoresContainer);
            wrapper.appendChild(analysisContainer);

            console.log('Speech analysis displayed:', speechAnalysis);
        }

        // Add TTS audio player if available (for assistant messages)
        if (role === 'assistant' && ttsAudio && ttsAudio.url) {
            const audioContainer = document.createElement('div');
            audioContainer.className = 'tts-audio-container';

            const audioElement = document.createElement('audio');
            audioElement.controls = true;
            audioElement.className = 'tts-audio-player';
            audioElement.src = ttsAudio.url;

            // Auto-play the TTS audio (with user interaction permission)
            audioElement.autoplay = true;
            audioElement.preload = 'auto';

            // Handle autoplay errors (browser may block autoplay without user interaction)
            audioElement.play().catch(error => {
                console.log('Auto-play blocked by browser. User must interact with the page first.', error);
            });

            const voiceLabel = document.createElement('span');
            voiceLabel.className = 'tts-voice-label';
            voiceLabel.textContent = `🔊 Voice: ${ttsAudio.voice_name || 'AI'}`;

            audioContainer.appendChild(voiceLabel);
            audioContainer.appendChild(audioElement);
            wrapper.appendChild(audioContainer);

            console.log('TTS audio added:', {
                url: ttsAudio.url,
                voice: ttsAudio.voice_name,
                duration: ttsAudio.duration,
                generationTime: ttsAudio.generation_time
            });
        }

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

    // Voice Settings Management
    async openVoiceSettings() {
        this.voiceSettingsModal.style.display = 'flex';
        await this.loadVoiceProfiles();
    }

    closeVoiceSettings() {
        this.voiceSettingsModal.style.display = 'none';
    }

    async loadVoiceProfiles() {
        this.voiceProfilesList.innerHTML = '<p class="loading-text">Loading voice profiles...</p>';

        try {
            const response = await fetch('/api/chat/voice-profiles/', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            });

            const result = await response.json();

            if (result.success && result.voice_profiles) {
                if (result.voice_profiles.length === 0) {
                    this.voiceProfilesList.innerHTML = '<p class="loading-text">No voice profiles available. Upload one below!</p>';
                    return;
                }

                this.voiceProfilesList.innerHTML = '';
                result.voice_profiles.forEach(profile => {
                    const profileDiv = document.createElement('div');
                    profileDiv.className = 'voice-profile-item';

                    const infoDiv = document.createElement('div');
                    infoDiv.className = 'voice-profile-info';

                    const nameDiv = document.createElement('div');
                    nameDiv.className = 'voice-profile-name';
                    nameDiv.textContent = profile.name;

                    const metaDiv = document.createElement('div');
                    metaDiv.className = 'voice-profile-meta';
                    metaDiv.textContent = `ID: ${profile.voice_id.substring(0, 8)}...`;

                    infoDiv.appendChild(nameDiv);
                    infoDiv.appendChild(metaDiv);

                    profileDiv.appendChild(infoDiv);

                    if (profile.is_default) {
                        const badge = document.createElement('span');
                        badge.className = 'voice-profile-badge';
                        badge.textContent = 'DEFAULT';
                        profileDiv.appendChild(badge);
                    }

                    this.voiceProfilesList.appendChild(profileDiv);
                });
            } else {
                this.voiceProfilesList.innerHTML = '<p class="loading-text">Failed to load voice profiles</p>';
            }

        } catch (error) {
            console.error('Error loading voice profiles:', error);
            this.voiceProfilesList.innerHTML = '<p class="loading-text">Error loading voice profiles</p>';
        }
    }

    async uploadVoiceProfile(event) {
        event.preventDefault();

        const nameInput = document.getElementById('voiceName');
        const audioFileInput = document.getElementById('voiceAudioFile');
        const setDefaultCheckbox = document.getElementById('setAsDefault');

        const formData = new FormData();
        formData.append('name', nameInput.value);
        formData.append('reference_audio', audioFileInput.files[0]);
        formData.append('set_as_default', setDefaultCheckbox.checked);

        try {
            const response = await fetch('/api/chat/upload-voice-profile/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                alert('Voice profile uploaded successfully!');
                // Reset form
                nameInput.value = '';
                audioFileInput.value = '';
                setDefaultCheckbox.checked = false;
                // Reload profiles and update quality mode state
                await this.loadVoiceProfiles();
                await this.checkVoiceProfiles();
            } else {
                alert(`Failed to upload voice profile: ${result.message}`);
            }

        } catch (error) {
            console.error('Error uploading voice profile:', error);
            alert('Error uploading voice profile. Please try again.');
        }
    }

    // Tab switching
    switchTab(tab) {
        if (tab === 'record') {
            this.recordTab.classList.add('active');
            this.uploadTab.classList.remove('active');
            this.recordContent.classList.add('active');
            this.uploadContent.classList.remove('active');
        } else {
            this.uploadTab.classList.add('active');
            this.recordTab.classList.remove('active');
            this.uploadContent.classList.add('active');
            this.recordContent.classList.remove('active');
        }
    }

    // Voice profile recording
    async startVoiceProfileRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.voiceProfileMediaRecorder = new MediaRecorder(stream);
            this.voiceProfileAudioChunks = [];

            this.voiceProfileMediaRecorder.addEventListener('dataavailable', (event) => {
                this.voiceProfileAudioChunks.push(event.data);
            });

            this.voiceProfileMediaRecorder.addEventListener('stop', () => {
                // Use the actual recorded MIME type from MediaRecorder
                const mimeType = this.voiceProfileMediaRecorder.mimeType || 'audio/webm';
                const audioBlob = new Blob(this.voiceProfileAudioChunks, { type: mimeType });
                this.recordedVoiceBlob = audioBlob;

                // Show preview
                const audioUrl = URL.createObjectURL(audioBlob);
                this.voicePreview.src = audioUrl;
                this.voicePreview.style.display = 'block';

                // Show form
                this.voiceRecordForm.style.display = 'block';
                this.recorderStatus.textContent = 'Recording saved! Enter details and save.';

                stream.getTracks().forEach(track => track.stop());
            });

            this.voiceProfileMediaRecorder.start();
            this.isVoiceProfileRecording = true;

            // Update UI
            this.startVoiceRecordBtn.style.display = 'none';
            this.stopVoiceRecordBtn.style.display = 'flex';
            this.voiceRecordTimer.style.display = 'flex';
            this.recorderStatus.textContent = 'Recording... Speak clearly for 6-30 seconds';

            // Start timer
            this.voiceProfileRecordingStartTime = Date.now();
            this.updateVoiceProfileRecordingTime();
            this.voiceProfileRecordingInterval = setInterval(() => this.updateVoiceProfileRecordingTime(), 1000);

        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Could not access microphone. Please check your browser permissions.');
        }
    }

    stopVoiceProfileRecording() {
        if (this.voiceProfileMediaRecorder && this.isVoiceProfileRecording) {
            this.voiceProfileMediaRecorder.stop();
            this.isVoiceProfileRecording = false;

            // Stop timer
            if (this.voiceProfileRecordingInterval) {
                clearInterval(this.voiceProfileRecordingInterval);
                this.voiceProfileRecordingInterval = null;
            }

            // Reset UI
            this.startVoiceRecordBtn.style.display = 'flex';
            this.stopVoiceRecordBtn.style.display = 'none';
            this.voiceRecordTimer.style.display = 'none';
        }
    }

    updateVoiceProfileRecordingTime() {
        if (!this.voiceProfileRecordingStartTime) return;

        const elapsed = Math.floor((Date.now() - this.voiceProfileRecordingStartTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        this.voiceRecordTime.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }

    async saveRecordedVoiceProfile(event) {
        event.preventDefault();

        if (!this.recordedVoiceBlob) {
            alert('No recording found. Please record your voice first.');
            return;
        }

        const nameInput = document.getElementById('voiceNameRecord');
        const setDefaultCheckbox = document.getElementById('setAsDefaultRecord');

        const formData = new FormData();
        formData.append('name', nameInput.value);

        // Use correct file extension based on blob type
        const fileExtension = this.recordedVoiceBlob.type.includes('webm') ? 'webm' : 'wav';
        formData.append('reference_audio', this.recordedVoiceBlob, `voice_recording_${Date.now()}.${fileExtension}`);
        formData.append('set_as_default', setDefaultCheckbox.checked);

        try {
            const response = await fetch('/api/chat/upload-voice-profile/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                alert('Voice profile created successfully!');
                // Reset everything
                this.cancelVoiceRecording();
                // Reload profiles and update quality mode state
                await this.loadVoiceProfiles();
                await this.checkVoiceProfiles();
            } else {
                alert(`Failed to create voice profile: ${result.message}`);
            }

        } catch (error) {
            console.error('Error saving voice profile:', error);
            alert('Error saving voice profile. Please try again.');
        }
    }

    cancelVoiceRecording() {
        // Reset recording state
        this.recordedVoiceBlob = null;
        this.voiceProfileAudioChunks = [];

        // Reset UI
        this.voicePreview.style.display = 'none';
        this.voicePreview.src = '';
        this.voiceRecordForm.style.display = 'none';
        this.recorderStatus.textContent = 'Ready to record (6-30 seconds recommended)';

        // Reset form
        document.getElementById('voiceNameRecord').value = '';
        document.getElementById('setAsDefaultRecord').checked = false;

        // Reset buttons
        this.startVoiceRecordBtn.style.display = 'flex';
        this.stopVoiceRecordBtn.style.display = 'none';
        this.voiceRecordTimer.style.display = 'none';
    }
}

// Initialize the chat application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const chat = new VoiceChat();
});
