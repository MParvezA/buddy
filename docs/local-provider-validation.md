# Buddy Local Provider Validation

## Outcome

Buddy now has opt-in, CPU-only local providers for terminal push-to-talk,
multilingual speech recognition, structured dialogue proposals, and
English/German speech synthesis. The existing deterministic providers remain
the defaults.

The frozen ROS contract remains version `0.1.0`. No provider gained access to a
movement topic, Navigation2 implementation, differential-drive controller, or
emergency-stop reset path.

## Implemented provider path

```text
WH-CH520 microphone
  → PipeWire bounded capture
  → whisper.cpp multilingual STT
  → RecognizedUtterance
  → llama.cpp structured proposal
  → frozen validator and confirmation
  → registered task execution
  → Piper English/German synthesis
  → PipeWire playback
```

The terminal push-to-talk process is deliberately separate from the main
launch because it owns interactive keyboard input. The main launch can accept
that external utterance source while composing the real model and speech
providers.

## Runtime assets used

The live development smoke used:

- llama.cpp built CPU-only from source;
- Qwen3 1.7B `Q4_K_M`;
- whisper.cpp multilingual `base`;
- Piper `en_US-lessac-medium`;
- Piper `de_DE-thorsten-medium`;
- the WH-CH520 PipeWire mSBC headset profile.

These binaries and model files live under ignored `runtime_assets/` and are not
part of the Git repository. Exact installation and launch commands are in
[the local-provider setup guide](local-provider-setup.md).

## Build and automated tests

The final workspace validation completed:

```text
16 packages built
242 tests
0 errors
0 failures
13 skipped
```

Tests ran sequentially in an isolated ROS domain and Gazebo partition. The 13
skips are the repository's documented ROS cppcheck blacklist, not disabled
provider or safety tests.

Provider-focused results include:

- `buddy_voice`: 72 passing tests;
- `buddy_brain`: 27 passing tests;
- `buddy_bringup`: 15 passing tests, including the root end-to-end flow;
- launch-contract checks proving real providers require explicit opt-in and
  the interactive terminal is not embedded in production composition.

The full suite also checks the ROS dependency graph, interface constants, TF
ownership, fake-provider end-to-end flow, capability rejection, action
cancellation, and motion safety contracts.

## Live provider evidence

### Local model

The real Qwen3 provider ran CPU-only with three inference threads, a 4096-token
context bound, and bounded output:

- valid completion latency: approximately `3.6 s`;
- peak resident memory: approximately `2.4 GiB`;
- exact controlled `Report your status` context produced a valid
  `report_status` plan;
- a separate schema-invalid model proposal was rejected before task execution.

llama.cpp output is written to an owner-only temporary file, parsed as one
assistant completion, then removed. Crash, timeout, shutdown, forged-delimiter,
surviving-descendant, and cleanup behavior are covered by tests.

### Voice

Piper synthesized and played:

```text
Hello. I am Buddy, and my local voice is working.
```

The resulting English audio was valid mono PCM at 22.05 kHz with a duration of
approximately `3.3 s`. The WH-CH520 exposed both microphone and speaker through
its mSBC profile.

A bounded five-second headset capture reached multilingual Whisper. The sample
contained no recognized speech; Whisper returned `[BLANK_AUDIO]`. Buddy now
rejects that sentinel as no utterance instead of forwarding it to dialogue.
This proves the device/capture/STT plumbing and fail-closed behavior, but it is
not evidence of a successful spoken English or German transcript.

Provider-owned microphone WAV, Whisper output, Piper WAV, and llama completion
files were absent after each completed or failed request.

Adversarial provider tests additionally prove:

- a non-reading Piper child cannot block cancellation or timeout while Buddy
  delivers a large input;
- provider files live in random private `0700` directories and reject
  symlinks, pre-existing targets, and oversized WAV/JSON outputs;
- voice and model children receive explicit environment allowlists rather than
  secret-bearing parent configuration;
- an exited provider launcher cannot leave a surviving descendant process
  group after timeout, cancellation, or shutdown.

### Full local composition

A headless production launch with real llama.cpp and Piper providers started
all 25 processes and exposed the frozen task, speech, and navigation actions.
After a `Report your status` utterance and confirmation:

- dialogue reported the real `llama_cpp` provider ready;
- all four capabilities and neighboring actions were ready;
- the task executive returned to ready and idle after execution;
- an invalid proposal from a prior utterance was rejected by the frozen schema
  validator.

This demonstrates real-model proposal, validation, confirmation, task
execution, and speech-server composition. It does not claim a successful
microphone transcript because the utterance was injected at the frozen
recognized-utterance boundary.

## Simulation and safety evidence

Dedicated isolated Gazebo checks passed:

- runtime sensor, simulation-clock, odometry, and TF contract;
- simulator-side command watchdog: moved `0.462 m`, then `0.000 m` after stale
  command expiry;
- production motion probe:
  - teleoperation won over navigation;
  - navigation resumed after teleoperation became stale;
  - controller odometry proved simulated physical movement;
  - stale input produced zero safe output;
  - emergency stop latched and overrode movement;
  - reset required the frozen acknowledged operator procedure.

Voice and brain were not involved in those safety decisions. Their packages
still contain no publisher for raw velocity, safe velocity, private Gazebo
drive input, or motor commands.

## Known limitations

- Continuous `Buddy` / `Hey Buddy` wake-word detection is not implemented yet;
  terminal push-to-talk is the first real input mode.
- A successful live spoken English and German transcription still needs an
  operator-driven demonstration.
- The host was configured to the four-core policy but was not memory-isolated
  to 8 GB. The measured model RSS fits comfortably, but complete-stack resource
  proof requires an 8 GB cgroup or target machine.
- The 1.7B model can produce schema-invalid proposals. This is expected to
  remain possible; strict validation and clarification are the safety
  boundary.
- One non-isolated full-provider launch observed simulator-clock traffic from
  another host process. Safety rejected stale timestamps. Dedicated
  `GZ_PARTITION` runs passed, so operators should keep an isolated Gazebo
  partition for reproducible testing.
- The minimal Gazebo world demonstrates planning and motion but not a
  repeatable terminal arrival at every named location.

## Recommended next slice

Add a local wake-word detector behind the existing audio-provider boundary,
playback ducking, and a repeatable English/German operator test under an
enforced 8 GB/four-core resource limit. Keep the frozen task, movement,
arbitration, and safety contracts unchanged.
