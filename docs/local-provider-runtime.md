# Buddy Local Provider Runtime

## Status

- Profile version: `0.1`
- Status: **FROZEN** for the first local-provider implementation round
- Parent ROS contract: `docs/contracts`, version `0.1.0`, unchanged
- Target: Ubuntu 24.04, four CPU cores, 8 GB RAM, no GPU
- Development audio: Sony WH-CH520 worn by the operator
- Languages: English and German
- Wake phrase: `Buddy` or `Hey Buddy`

This profile defines implementation and launch configuration below the frozen
ROS boundary. It does not grant the voice or model layers any additional robot
authority.

## Architectural invariants

1. Fake providers remain the default for simulation and automated tests.
2. Real providers are selected explicitly and fail closed when a binary,
   model, audio device, or local process is unavailable.
3. Voice and model providers publish no movement command.
4. Model output still crosses the existing strict task-plan validator.
5. Spoken emergency-stop detection remains deterministic and outside the
   language model.
6. Audio, STT, TTS, and model inference may fail without affecting the command
   arbiter, safety filter, controller watchdog, or emergency stop.
7. Native provider processes use argument vectors, never a shell command.
8. Provider timeouts use steady time and terminate owned child processes.
9. No provider listens on a non-loopback network address.
10. No audio, transcript, or dialogue history is retained by default.

## Ownership

| Owner | Paths | Responsibility |
| --- | --- | --- |
| Voice | `buddy_voice/**` | PipeWire capture/playback, push-to-talk, wake-word boundary, whisper.cpp and Piper adapters |
| Brain | `buddy_brain/**` | llama.cpp completion adapter, prompt boundary, model health |
| Root | `buddy_bringup/**`, `docs/**` | Composition, resource profile, setup documentation, integration tests |

Neither worker may change `buddy_interfaces`, `buddy_safety`, `buddy_base`,
navigation packages, root build/CI files, or the frozen ROS contract.

## Runtime modes

### Deterministic mode

Used by the production simulation launch until real providers are explicitly
requested. It retains the existing fake audio, STT, TTS, and model behavior.

### Local development mode

Real audio input runs in an interactive terminal so that push-to-talk can read
the operator's keyboard without assuming a desktop toolkit or adding a ROS
trigger interface. The WH-CH520 is selected through PipeWire's configured
default source and sink unless an explicit device is supplied.

The initial interaction is:

```text
press Enter
  → bounded microphone capture
  → press Enter or maximum duration
  → whisper.cpp multilingual transcription
  → frozen RecognizedUtterance
  → bounded model proposal and validation
  → Piper English/German synthesis
  → PipeWire playback
```

Wake-word mode remains behind the same `AudioInputProvider` boundary. It may be
enabled only when a tested local `Buddy` model is configured. Wake-word
detection opens one bounded utterance capture; it does not bypass STT,
deterministic emergency-stop detection, dialogue validation, or confirmation.

## Voice provider configuration

| Setting | Default | Bound |
| --- | --- | --- |
| Capture binary | `pw-record` | Absolute resolution required before execution |
| Playback binary | `pw-play` | Absolute resolution required before execution |
| Audio format | 16-bit PCM WAV | 16 kHz, mono |
| Audio source/sink | PipeWire default | Explicit override allowed |
| Input mode | Push-to-talk | Wake word requires configured model |
| Maximum capture | 15 seconds | 1–30 seconds |
| STT runtime | `whisper-cli` | Local executable only |
| STT model | multilingual `base` | Explicit existing file |
| STT threads | 2 | 1–3 |
| STT timeout | 30 seconds | 1–60 seconds |
| STT language | automatic | English or German hints allowed |
| TTS runtime | `piper` | Local executable only |
| TTS voices | one `en_*`, one `de_*` | Explicit model/config files |
| TTS synthesis timeout | 15 seconds | 1–30 seconds |
| TTS playback timeout | 30 seconds | 1–60 seconds |

The dialogue layer selects German speech for a German final utterance and
English otherwise. An explicit registered `speak` capability voice argument
may override this selection when it names a configured voice.

## Model provider configuration

| Setting | Default | Bound |
| --- | --- | --- |
| Runtime | `llama.cpp` | Local child process or loopback server |
| Model | Qwen3 1.7B, Q4 | Explicit existing GGUF file |
| Fallback | Qwen3 0.6B, Q8 | Explicit operator selection |
| Threads | 3 | 1–3 |
| Context | 4096 tokens | 512–4096 |
| Generated tokens | 256 | 32–256 |
| Requests | one at a time | No unbounded queue |
| Completion timeout | 20 seconds | 1–60 seconds |
| Temperature | 0.1 | 0.0–0.3 |
| Network | none or loopback only | Never externally bound |

The prompt contains only the controlled status summary, world summary,
registered capability schemas, current utterance, and exact JSON response
schema. The model cannot create identifiers, invoke a capability, execute
code, read files, or send ROS messages.

## Resource policy

- Provider configuration assumes at most four available CPU cores even when
  the host exposes more.
- llama.cpp receives no more than three inference threads.
- whisper.cpp receives no more than two threads by default.
- STT and model work are sequential for one dialogue turn.
- Context and output limits are mandatory.
- Child processes inherit no secret-bearing configuration beyond their explicit
  environment allowlist.
- A model process timeout is a dialogue failure, not a robot task timeout.
- Model and audio files are runtime assets and are not committed to Git.

The complete operating system, ROS, Gazebo, and provider stack is targeted at
8 GB RAM. Provider tests validate the configured bounds; a runtime smoke test
must measure real resident memory before this profile is considered proven on
different hardware.

## Diagnostics and recovery

Provider diagnostics use the existing reliable `/diagnostics` topic:

- Voice input reports capture and STT readiness and the last bounded error.
- Speech output reports missing voice, synthesis, playback, cancellation, and
  timeout failures.
- Dialogue reports model provider identity, readiness, timeout, malformed
  output, and recovery.

Provider failure never fabricates an utterance, successful task, or successful
speech result. The next valid interaction may recover without restarting the
safety or motion stack.

## Acceptance criteria

1. Deterministic simulation and all existing tests remain unchanged by default.
2. Concrete provider tests use fake executables/modules and require no model,
   audio device, network, or GPU.
3. Every child-process argument, timeout, exit code, output file, and cleanup
   path is tested.
4. German and English transcript/voice selection is tested.
5. Cancellation terminates TTS playback and deletes temporary audio.
6. Model timeout, crash, invalid JSON, and schema-invalid JSON are structured
   failures with no task execution.
7. Repository scans still find no movement publisher in voice or brain.
8. Full workspace build and sequential test suite pass.
9. An optional live smoke test reports unavailable dependencies as a clear
   skip or diagnostic, never as success.

