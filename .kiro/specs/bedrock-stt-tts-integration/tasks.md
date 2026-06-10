# Implementation Plan: Bedrock STT/TTS Integration

## Overview

This plan implements the integration of Amazon Transcribe (STT), Amazon Polly (TTS), enhanced Bedrock and Edge LLM clients, and a Demo Runner into the Speechless voice assistant. The implementation follows a bottom-up approach: shared infrastructure first (AWS session, config, models), then individual components (STT, TTS, LLM clients), then routing/orchestration, and finally the demo runner that wires everything together.

## Tasks

- [ ] 1. Set up AWS session infrastructure and data models
  - [ ] 1.1 Create AWSSessionManager class in `speechless/cloud/aws_session.py`
    - Implement `AWSSessionManager` with single boto3 Session initialized from `SPEECHLESS_BEDROCK_PROFILE` (default: "losrudos") and `SPEECHLESS_BEDROCK_REGION` (default: "us-east-1")
    - Create Transcribe, Polly, and Bedrock Runtime clients independently with error isolation
    - Expose `transcribe_client`, `polly_client`, `bedrock_client` as Optional properties (None when unavailable)
    - Implement `is_service_available(service: str) -> bool`
    - Handle session-level credential failures (mark all services unavailable) and individual client failures (mark only that service unavailable)
    - Log errors without blocking pipeline initialization
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 1.2 Write property tests for AWS session failure isolation
    - **Property 11: AWS session failure degrades all cloud services**
    - **Validates: Requirements 6.4**
    - **Property 12: Individual client failure degrades only that service**
    - **Validates: Requirements 6.5**

  - [ ] 1.3 Update `speechless/config.py` with new configuration fields
    - Add `transcribe_timeout: float = 5.0`
    - Add `polly_timeout: float = 5.0`
    - Add `edge_llm_timeout: float = 10.0`
    - Add `max_conversation_turns: int = 20`
    - Add `polly_max_text_chars: int = 3000`
    - Add `audio_max_file_size_mb: int = 15`
    - Add `audio_min_duration_sec: float = 0.5`
    - Add `audio_max_duration_sec: float = 30.0`
    - _Requirements: 1.4, 2.6, 3.3, 7.4, 7.5, 7.6_

  - [ ] 1.4 Add new dataclasses to `speechless/models.py`
    - Add `AudioValidationResult(samples, sample_rate, duration_seconds, error, converted)`
    - Add `SceneResult(scene_number, passed, stt_latency_ms, classification_latency_ms, llm_latency_ms, tts_latency_ms, total_latency_ms, error, performance_target_met)`
    - Add `SceneConfig(scene_number, audio_file, expected_mode, connectivity_transition, performance_target_ms, description)`
    - _Requirements: 5.1, 5.6, 7.1_

- [ ] 2. Implement AudioValidator
  - [ ] 2.1 Create `speechless/speech/audio_validator.py`
    - Implement `AudioValidator` with constants: MAX_FILE_SIZE_BYTES (15MB), MIN_DURATION_SEC (0.5), MAX_DURATION_SEC (30.0), EXPECTED_SAMPLE_RATE (16000), EXPECTED_CHANNELS (1), EXPECTED_SAMPLE_WIDTH (2)
    - Implement `validate_and_load(file_path: str) -> AudioValidationResult` with validation order: file exists → file size → WAV format detection → conversion if needed → duration check → return float32 samples
    - Implement `convert_audio(file_path: str) -> AudioValidationResult` with 10-second timeout for format conversion to 16kHz mono 16-bit PCM
    - Return clear error messages indicating violated constraints and supported formats
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 2.2 Write property tests for AudioValidator
    - **Property 10: WAV file read produces float32 array with correct properties**
    - **Validates: Requirements 5.1, 7.1**
    - **Property 13: Audio file validation rejects invalid files correctly**
    - **Validates: Requirements 7.1, 7.4, 7.5, 7.6**
    - **Property 14: Audio format conversion produces standard output**
    - **Validates: Requirements 7.2**

- [ ] 3. Implement TranscribeSTT (Cloud STT replacement)
  - [ ] 3.1 Replace `speechless/speech/stt_cloud.py` with TranscribeSTT implementation
    - Implement `TranscribeSTT(client, timeout=5.0)` using the Transcribe client from AWSSessionManager
    - Implement `transcribe(audio_samples: np.ndarray, sample_rate: int = 16000) -> Optional[TranscriptionResult]`
    - Implement `numpy_to_wav_bytes(samples: np.ndarray, sample_rate: int = 16000) -> bytes` converting float32 to 16-bit PCM WAV
    - Return `TranscriptionResult(text, confidence, source="cloud")` on success, `None` on error/timeout
    - Use 5-second timeout; catch and log all exceptions
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6_

  - [ ]* 3.2 Write property tests for TranscribeSTT
    - **Property 1: Audio float32-to-WAV conversion preserves sample count and format**
    - **Validates: Requirements 1.5**
    - **Property 2: Transcribe response parsing produces correct TranscriptionResult**
    - **Validates: Requirements 1.2**

- [ ] 4. Implement PollyTTS and TTSRouter
  - [ ] 4.1 Create `speechless/response/polly_tts.py`
    - Implement `PollyTTS(client, voice_id="Joanna", timeout=5.0)`
    - Implement `synthesize(text: str) -> Optional[bytes]` returning PCM bytes (signed 16-bit LE, 16kHz) or None on error
    - Implement `truncate_text(text: str, max_chars: int = 3000) -> str` truncating at last sentence boundary (., !, ?) within limit
    - Use neural engine, Joanna voice, SampleRate="16000", OutputFormat="pcm"
    - 5-second timeout; return None on any error
    - _Requirements: 2.1, 2.2, 2.3, 2.6_

  - [ ]* 4.2 Write property test for text truncation
    - **Property 5: Text truncation preserves sentence boundaries and length limit**
    - **Validates: Requirements 2.6**

  - [ ] 4.3 Create `speechless/response/tts_router.py`
    - Implement `TTSRouter(polly_tts: Optional[PollyTTS], local_tts: ResponseEngine)`
    - Implement `speak(text: str, mode: ProcessingMode) -> None`
    - OFFLINE mode → always use local TTS
    - ONLINE mode → attempt Polly, fallback to local TTS on error (pass identical text)
    - _Requirements: 2.4, 2.5_

  - [ ]* 4.4 Write property tests for TTSRouter
    - **Property 3: Polly error triggers fallback to local TTS**
    - **Validates: Requirements 2.4**
    - **Property 4: Offline mode routes exclusively to local TTS**
    - **Validates: Requirements 2.5**

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Enhance EdgeLLMClient with real requests and history
  - [ ] 6.1 Enhance `speechless/edge/edge_llm.py` with conversation history support
    - Add `generate_with_history(user_message: str, conversation_history: list[dict], max_history_turns: int = 20) -> EdgeLLMResponse`
    - Cap history at 20 turns, trimming oldest first when exceeding limit
    - Always include system prompt as first message (role="system") identifying the assistant as an in-vehicle voice assistant
    - Use model name from `SPEECHLESS_EDGE_MODEL_NAME` env var (default: "local-model")
    - Use endpoint from `SPEECHLESS_EDGE_LM_URL` env var (default: "http://localhost:1234/v1")
    - 10-second timeout; return `EdgeLLMResponse(success=False, error_message=...)` on failure
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 6.2 Write property tests for EdgeLLMClient
    - **Property 6: Edge LLM messages always include system prompt**
    - **Validates: Requirements 3.2**
    - **Property 7: Conversation history is capped at 20 turns**
    - **Validates: Requirements 3.3**

- [ ] 7. Enhance BedrockClient with telemetry and context lifecycle
  - [ ] 7.1 Enhance `speechless/cloud/bedrock_client.py` with telemetry-aware converse
    - Add `converse_with_telemetry(user_message: str, telemetry: Optional[dict] = None, history: Optional[list] = None) -> BedrockResponse`
    - Implement `_build_system_prompt(telemetry: Optional[dict]) -> Optional[str]` — include only non-None telemetry fields; omit system prompt entirely if all fields are None
    - Support injected offline context: include as preceding turns in converse request
    - Clear injected context after successful request; retain on failure
    - Use "losrudos" profile via AWSSessionManager, connect timeout 3s, read timeout 5s
    - Default model: `anthropic.claude-3-haiku-20240307-v1:0` in us-east-1
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 7.2 Write property tests for BedrockClient
    - **Property 8: Telemetry system prompt includes only non-None fields**
    - **Validates: Requirements 4.2, 4.3**
    - **Property 9: Injected context cleared on success, retained on failure**
    - **Validates: Requirements 4.5**

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement DemoRunner and wire pipeline
  - [ ] 9.1 Wire all components together in `speechless/main.py`
    - Initialize AWSSessionManager and create all clients
    - Replace existing CloudSTT instantiation with TranscribeSTT
    - Create PollyTTS and TTSRouter (with existing pyttsx3 as fallback)
    - Wire enhanced EdgeLLMClient and BedrockClient into the pipeline
    - Integrate AudioValidator for file input processing
    - Ensure local STT fallback when cloud STT confidence < 0.7 threshold
    - _Requirements: 1.3, 6.1, 6.2, 6.3_

  - [ ] 9.2 Create `speechless/demo/demo_runner.py` with DemoRunner class
    - Implement `DemoRunner(pipeline, audio_dir, connectivity_monitor)`
    - Implement `run_all_scenes() -> list[SceneResult]` executing all 10 demo scenes in order
    - Implement `run_scene(scene_number, audio_path, ...) -> SceneResult` with timing metrics (STT, classification, LLM, TTS, total latency in ms)
    - Implement `print_summary(results)` reporting passed/failed counts and performance target violations
    - Handle connectivity transitions: toggle ConnectivityMonitor state before scenes that require it, wait for mode confirmation
    - Skip scenes with file-related errors (missing, unreadable, wrong format) and continue; log all other scene errors but also continue
    - Flag scenes exceeding performance targets: vehicle control <1000ms, informational <5000ms, edge LLM <3000ms, classification <100ms
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ] 9.3 Create `scripts/run_demo.py` entry point
    - Parse optional `--audio-dir` argument (default: `audio/demo/`)
    - Initialize pipeline with AWSSessionManager
    - Run all scenes via DemoRunner and print summary
    - _Requirements: 5.4_

  - [ ]* 9.4 Write integration tests for DemoRunner
    - Test full pipeline: WAV → STT → Classification → LLM → TTS with mocked AWS services
    - Test scene skipping on file errors
    - Test connectivity transitions between scenes
    - Test performance timing measurement
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis (already in dev dependencies)
- Unit tests validate specific examples and edge cases
- The project uses Python 3.11+ with boto3, numpy, and existing test infrastructure (pytest + hypothesis)
- Source code lives in `speechless/` (not `src/speechless/`)
- Existing tests are in `tests/` with conftest.py fixtures

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3", "1.4"] },
    { "id": 1, "tasks": ["1.2", "2.1", "3.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "4.2", "4.3"] },
    { "id": 3, "tasks": ["4.4", "6.1", "7.1"] },
    { "id": 4, "tasks": ["6.2", "7.2", "9.1"] },
    { "id": 5, "tasks": ["9.2", "9.3"] },
    { "id": 6, "tasks": ["9.4"] }
  ]
}
```
