# Requirements Document

## Introduction

This feature integrates AWS Bedrock-based Speech-to-Text (Amazon Transcribe) and Text-to-Speech (Amazon Polly) services into the Speechless voice assistant, replacing the current OpenAI Whisper API for cloud STT and adding a cloud TTS option alongside the existing pyttsx3 offline engine. Additionally, this feature ensures the demo pipeline makes real LLM requests to both the edge (LM Studio) and cloud (Bedrock converse API) backends, producing end-to-end audio-in → text → LLM → audio-out flows for the scripted demo.

## Glossary

- **Pipeline**: The Speechless voice assistant processing pipeline (IDLE → LISTENING → TRANSCRIBING → CLASSIFYING → EXECUTING → RESPONDING)
- **Cloud_STT**: The cloud-based speech-to-text module that transcribes audio when local STT confidence is below threshold
- **Cloud_TTS**: The cloud-based text-to-speech module that synthesizes spoken audio from LLM response text
- **Local_STT**: The faster-whisper based on-device speech-to-text module
- **Local_TTS**: The pyttsx3-based offline text-to-speech engine
- **Bedrock_Client**: The AWS Bedrock converse API client authenticated via the "losrudos" AWS profile
- **Edge_LLM**: The OpenAI-compatible LLM client targeting LM Studio or Jetson
- **Transcribe_Client**: The AWS Amazon Transcribe client for cloud speech-to-text
- **Polly_Client**: The AWS Amazon Polly client for cloud text-to-speech synthesis
- **Demo_Runner**: The orchestration script that executes the scripted demo scenarios end-to-end
- **Audio_Input**: A pre-recorded audio file (WAV format, 16kHz mono) representing a driver utterance
- **Connectivity_Monitor**: The component that detects online/offline state transitions

## Requirements

### Requirement 1: Replace Cloud STT with Amazon Transcribe

**User Story:** As a demo operator, I want cloud speech-to-text to use Amazon Transcribe via the "losrudos" AWS profile, so that the system uses a unified AWS backend instead of requiring a separate OpenAI API key.

#### Acceptance Criteria

1. WHILE the system is in ONLINE mode, WHEN the Pipeline receives an Audio_Input, THE Cloud_STT SHALL send the audio to Amazon Transcribe for transcription using a boto3 session initialized with the "losrudos" AWS profile
2. WHEN Amazon Transcribe returns a transcription result, THE Cloud_STT SHALL return a TranscriptionResult with the transcribed text, the confidence score from the top-ranked alternative provided by Amazon Transcribe (value between 0.0 and 1.0), and source set to "cloud"
3. IF the Local_STT transcription confidence is below the configured threshold (default 0.7), THEN THE Pipeline SHALL invoke the Cloud_STT as a fallback
4. IF Amazon Transcribe returns an error or the request does not complete within a 5-second timeout, THEN THE Cloud_STT SHALL return None and the Pipeline SHALL use the Local_STT result as the final transcription
5. THE Cloud_STT SHALL accept audio as a numpy float32 array (16kHz, mono) and convert it to WAV format (16kHz, mono, 16-bit PCM) before sending to Amazon Transcribe
6. IF the "losrudos" AWS profile is not configured or AWS credentials are invalid, THEN THE Cloud_STT SHALL return None on transcription attempts and the Pipeline SHALL use the Local_STT result

### Requirement 2: Add Cloud TTS with Amazon Polly

**User Story:** As a demo operator, I want cloud text-to-speech using Amazon Polly, so that the demo produces natural-sounding voice output when online without relying solely on pyttsx3.

#### Acceptance Criteria

1. WHILE the system is in ONLINE mode, WHEN the Pipeline produces a response text, THE Cloud_TTS SHALL synthesize speech audio using Amazon Polly via the "losrudos" AWS profile and return audible output within 3 seconds of receiving the text.
2. THE Cloud_TTS SHALL use the Amazon Polly neural voice engine with a female English (US) voice and an output sample rate of 16000 Hz.
3. WHEN the Cloud_TTS receives text of up to 3000 characters, THE Polly_Client SHALL return audio data in PCM format (signed 16-bit little-endian) for playback through sounddevice.
4. IF Amazon Polly returns an error or does not respond within 5 seconds, THEN THE Pipeline SHALL fall back to the Local_TTS (pyttsx3) for audio output of the same response text without requiring user intervention.
5. WHILE the system is in OFFLINE mode, THE Pipeline SHALL use the Local_TTS exclusively for speech output.
6. IF the response text exceeds 3000 characters, THEN THE Cloud_TTS SHALL truncate the text at the last complete sentence within the 3000-character limit before sending it to Amazon Polly.

### Requirement 3: Configure Edge LLM for Real Demo Requests

**User Story:** As a demo operator, I want the edge LLM path to make real requests to LM Studio running locally, so that offline demo scenarios produce actual LLM-generated responses.

#### Acceptance Criteria

1. WHEN the Pipeline routes a command to "edge" during the demo, THE Edge_LLM SHALL send a real chat completion request to LM Studio at the endpoint configured via SPEECHLESS_EDGE_LM_URL environment variable (default: http://localhost:1234/v1)
2. WHEN the Edge_LLM builds a request, THE Edge_LLM SHALL include a system prompt message with role "system" that identifies the assistant as an in-vehicle voice assistant
3. WHILE the system is in OFFLINE mode with an active multi-turn conversation, WHEN a new user message is received, THE Edge_LLM SHALL include up to 20 prior conversation turns (oldest trimmed first when exceeding the limit) in the chat completion request to maintain coherence
4. IF LM Studio is not running, does not respond within 10 seconds, returns an HTTP error, or returns a malformed response, THEN THE Edge_LLM SHALL return a response with success set to false and an error message indicating the nature of the failure
5. THE Edge_LLM SHALL use the model name configured via SPEECHLESS_EDGE_MODEL_NAME environment variable, defaulting to "local-model" when the variable is not set
6. WHEN the Edge_LLM receives a successful response from LM Studio, THE Edge_LLM SHALL return the generated text content from the first completion choice with success set to true

### Requirement 4: Configure Cloud LLM for Real Demo Requests

**User Story:** As a demo operator, I want the cloud LLM path to make real Bedrock converse API requests, so that online demo scenarios produce actual cloud-generated responses.

#### Acceptance Criteria

1. WHEN the Pipeline routes a command to "cloud" during the demo, THE Bedrock_Client SHALL send a real converse API request to the configured model (default: anthropic.claude-3-haiku-20240307-v1:0) in us-east-1
2. IF vehicle telemetry (latitude, longitude, fuel level, connectivity state) is available from the TelemetryReader, THEN THE Bedrock_Client SHALL include a system prompt containing those telemetry values as vehicle context in the converse API request
3. IF one or more telemetry fields are unavailable (None), THEN THE Bedrock_Client SHALL include only the available fields in the system prompt and omit the unavailable ones
4. WHEN transitioning from OFFLINE to ONLINE, THE Bedrock_Client SHALL include the injected offline conversation messages (from inject_context) as preceding turns in the converse API request, ordered chronologically before the new user message
5. WHEN the Bedrock_Client has sent a converse API request that includes injected offline context and the request succeeds, THE Bedrock_Client SHALL clear the injected context so subsequent requests do not repeat it. IF the request fails or times out, THEN THE Bedrock_Client SHALL retain the injected context for the next attempt
6. IF Bedrock returns an error or the request exceeds the 5-second read timeout, THEN THE Bedrock_Client SHALL return a BedrockResponse with success=False and an error_message indicating the failure type and cause
7. THE Bedrock_Client SHALL authenticate using the "losrudos" AWS CLI profile via boto3 Session with a connect timeout of 3 seconds

### Requirement 5: End-to-End Demo Audio Pipeline

**User Story:** As a demo operator, I want to provide pre-recorded audio files as input and hear synthesized speech output for each demo scene, so that the demo runs end-to-end with real speech services.

#### Acceptance Criteria

1. WHEN the Demo_Runner receives an Audio_Input file path, THE Pipeline SHALL read the WAV file (16kHz, mono, 16-bit PCM) and pass audio samples to the STT module for transcription within 500 milliseconds of file read initiation
2. IF the Audio_Input file path is missing, unreadable, or not in the expected WAV format (16kHz, mono, 16-bit PCM), THEN THE Pipeline SHALL log an error indicating the file path and failure reason, skip the current scene, and continue to the next scene in the demo script
3. WHEN the STT module returns a transcription, THE Pipeline SHALL route the text through classification, LLM processing (edge or cloud based on Connectivity_Monitor state), and TTS output in sequence, completing the full chain before processing the next scene
4. THE Demo_Runner SHALL support executing all 10 scenes from docs/demo_script.md in order using pre-recorded Audio_Input files, reporting a final summary that includes the count of scenes passed (TTS output produced) and scenes failed (error or timeout)
5. WHEN a scene requires a connectivity transition, THE Demo_Runner SHALL toggle the Connectivity_Monitor state to the required value and wait until the Pipeline confirms the new processing mode before processing the next Audio_Input
6. THE Demo_Runner SHALL log each pipeline step with timing metrics in milliseconds (STT latency, classification latency, LLM latency, TTS latency, total end-to-end latency) and flag any scene that exceeds its performance target: vehicle control less than 1000ms end-to-end, informational less than 5000ms, edge LLM less than 3000ms, classification less than 100ms

### Requirement 6: Unified AWS Session Management

**User Story:** As a developer, I want all AWS services (Transcribe, Polly, Bedrock) to share a single authenticated session configuration, so that credential management is centralized and consistent.

#### Acceptance Criteria

1. THE Pipeline SHALL create all AWS service clients (Transcribe, Polly, Bedrock Runtime) from a single boto3 Session instance initialized with the profile specified by the SPEECHLESS_BEDROCK_PROFILE environment variable (default: "losrudos")
2. THE Pipeline SHALL use the SPEECHLESS_BEDROCK_REGION environment variable (default: us-east-1) as the region for all AWS service clients created from the shared session
3. WHEN the Pipeline initializes, THE Pipeline SHALL read SPEECHLESS_BEDROCK_PROFILE and SPEECHLESS_BEDROCK_REGION once and create all three AWS clients (Transcribe, Polly, Bedrock Runtime) using the same session and region values
4. IF the AWS session initialization fails due to missing or invalid credentials or results in an undefined state, THEN THE Pipeline SHALL attempt to log an error message indicating the credential failure reason and set all cloud service references (Cloud_STT, Cloud_TTS, Bedrock_Client) to unavailable so that the Pipeline operates using Local_STT and Local_TTS exclusively. THE Pipeline SHALL proceed with local-only operation even if error logging itself fails
5. IF any individual AWS client creation fails after successful session initialization, THEN THE Pipeline SHALL log an error message identifying the failing service and mark only that service as unavailable while other successfully created clients remain operational

### Requirement 7: Audio Input File Format Support

**User Story:** As a demo operator, I want to provide audio files in standard WAV format, so that I can generate demo inputs using common recording tools.

#### Acceptance Criteria

1. THE Pipeline SHALL accept audio input files in WAV format with 16kHz sample rate, mono channel, and 16-bit PCM encoding, and SHALL reject files that do not also satisfy the duration and file size constraints defined in criteria 4, 5, and 6
2. WHEN an Audio_Input file does not match the expected WAV format (sample rate, channel count, or bit depth differ), THE Pipeline SHALL attempt to convert the audio to 16kHz mono 16-bit PCM within 10 seconds before processing
3. IF audio format conversion fails or the Audio_Input file is in an unrecognized format, THEN THE Pipeline SHALL return an error indicating the expected format requirements (16kHz, mono, 16-bit PCM WAV) and list the supported input formats
4. THE Pipeline SHALL support Audio_Input files with duration between 0.5 seconds and 30 seconds
5. IF an Audio_Input file has a duration shorter than 0.5 seconds or longer than 30 seconds, THEN THE Pipeline SHALL reject the file and return an error indicating the accepted duration range
6. THE Pipeline SHALL reject Audio_Input files exceeding 15 MB in size and return an error indicating the maximum allowed file size
