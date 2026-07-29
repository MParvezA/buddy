# Local Voice Assistant Setup

This guide runs Buddy's first real local-assistant slice on Ubuntu 24.04 with
four CPU cores, 8 GB RAM, and no GPU. It uses terminal push-to-talk, local
Whisper speech recognition, Qwen task proposals through llama.cpp, and local
Piper speech.

The default simulation launch still uses deterministic fake providers. Real
providers must be selected explicitly.

## Current scope

Implemented:

- WH-CH520 input and output through PipeWire;
- interactive terminal push-to-talk;
- automatic English/German transcription;
- a CPU-only Qwen3 1.7B Q4_K_M proposal provider;
- English and German Piper voices;
- bounded subprocesses, cleanup, cancellation, and diagnostics;
- the existing deterministic spoken emergency-stop boundary.

Not implemented yet:

- continuous listening;
- a production `Buddy`/`Hey Buddy` wake-word model;
- echo cancellation while Buddy is speaking;
- retaining conversation or audio between runs.

Push-to-talk is intentional for the first live slice. A wake-word provider must
later enter through the existing voice-provider boundary; it cannot gain task
or motion authority.

## Runtime assets

All assets live in ignored `runtime_assets/`. `COLCON_IGNORE` is required so
ROS package discovery does not inspect Python packages inside the Piper virtual
environment.

The tested versions are:

| Component | Tested version |
| --- | --- |
| llama.cpp | `60bccc3763395e01b039aa1ddeacc8cc0ea69f70` |
| whisper.cpp | `a630b35c6fc02c8879f751ec3f39a61327f01dc7` |
| Piper | `piper-tts==1.6.0` |
| LLM | `bartowski/Qwen_Qwen3-1.7B-GGUF`, `Q4_K_M` |
| STT | whisper.cpp multilingual `base` |
| English voice | `en_US-lessac-medium` |
| German voice | `de_DE-thorsten-medium` |

Qwen3 is free under its upstream model license. The selected Q4_K_M is a
community quantization of the upstream Qwen model. Piper and every voice/model
also have their own license or model card; review those before redistribution.

## One-time installation

Start in the repository:

```bash
cd /home/syncrobot/buddy
mkdir -p runtime_assets/src runtime_assets/models runtime_assets/voices
touch runtime_assets/COLCON_IGNORE
```

Build the two CPU-only native runtimes, never using more than four build jobs:

```bash
git clone https://github.com/ggml-org/llama.cpp.git runtime_assets/src/llama.cpp
git -C runtime_assets/src/llama.cpp checkout 60bccc3763395e01b039aa1ddeacc8cc0ea69f70
cmake -S runtime_assets/src/llama.cpp \
  -B runtime_assets/src/llama.cpp/build \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=ON \
  -DGGML_CUDA=OFF
cmake --build runtime_assets/src/llama.cpp/build \
  --target llama-cli \
  -j4
```

```bash
git clone https://github.com/ggml-org/whisper.cpp.git runtime_assets/src/whisper.cpp
git -C runtime_assets/src/whisper.cpp checkout a630b35c6fc02c8879f751ec3f39a61327f01dc7
cmake -S runtime_assets/src/whisper.cpp \
  -B runtime_assets/src/whisper.cpp/build \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=ON \
  -DGGML_CUDA=OFF
cmake --build runtime_assets/src/whisper.cpp/build \
  --target whisper-cli \
  -j4
```

Install Piper only inside the ignored project virtual environment:

```bash
python3 -m venv runtime_assets/piper-venv
runtime_assets/piper-venv/bin/pip install piper-tts==1.6.0
```

Download the selected assets:

```bash
curl -L --fail -o runtime_assets/models/Qwen_Qwen3-1.7B-Q4_K_M.gguf \
  https://huggingface.co/bartowski/Qwen_Qwen3-1.7B-GGUF/resolve/main/Qwen_Qwen3-1.7B-Q4_K_M.gguf
curl -L --fail -o runtime_assets/models/ggml-base.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin
```

```bash
curl -L --fail -o runtime_assets/voices/en_US-lessac-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
curl -L --fail -o runtime_assets/voices/en_US-lessac-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
curl -L --fail -o runtime_assets/voices/de_DE-thorsten-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx
curl -L --fail -o runtime_assets/voices/de_DE-thorsten-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json
```

Build Buddy:

```bash
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install \
  --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
source install/setup.bash
```

The explicit Python path avoids selecting an unrelated user-local Python that
does not contain ROS 2's build modules.

## Prepare the WH-CH520

The headset's normal A2DP profile provides high-quality playback but no
microphone source. Switch it to its mSBC headset profile during voice
development:

```bash
wpctl status
pw-cli enum-params DEVICE_ID EnumProfile
wpctl set-profile DEVICE_ID PROFILE_INDEX
wpctl status
```

For the tested session, `DEVICE_ID` was `61` and the
`headset-head-unit-msbc` profile index was `261`. PipeWire IDs can change after
reconnection or reboot, so inspect them instead of hard-coding those numbers.
The headset profile lowers playback quality while its microphone is active.

## Run Buddy

Open two terminals.

Terminal 1 starts Gazebo and all non-interactive layers with real model and
speech providers:

```bash
cd /home/syncrobot/buddy
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch buddy_bringup simulation.launch.py \
  voice_input_mode:=external \
  speech_provider:=piper \
  model_provider:=llama_cpp \
  llama_cpp_binary:=/home/syncrobot/buddy/runtime_assets/src/llama.cpp/build/bin/llama-cli \
  llama_cpp_model:=/home/syncrobot/buddy/runtime_assets/models/Qwen_Qwen3-1.7B-Q4_K_M.gguf \
  piper_binary:=/home/syncrobot/buddy/runtime_assets/piper-venv/bin/piper \
  piper_en_model:=/home/syncrobot/buddy/runtime_assets/voices/en_US-lessac-medium.onnx \
  piper_en_config:=/home/syncrobot/buddy/runtime_assets/voices/en_US-lessac-medium.onnx.json \
  piper_de_model:=/home/syncrobot/buddy/runtime_assets/voices/de_DE-thorsten-medium.onnx \
  piper_de_config:=/home/syncrobot/buddy/runtime_assets/voices/de_DE-thorsten-medium.onnx.json
```

Terminal 2 owns the keyboard and microphone:

```bash
cd /home/syncrobot/buddy
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run buddy_voice terminal_ptt -- \
  --whisper-binary /home/syncrobot/buddy/runtime_assets/src/whisper.cpp/build/bin/whisper-cli \
  --whisper-model /home/syncrobot/buddy/runtime_assets/models/ggml-base.bin \
  --stt-language auto \
  --stt-threads 2 \
  --ros-args -p use_sim_time:=true
```

Press Enter once to start recording, speak English or German, then press Enter
again to transcribe. `Ctrl-C` exits.

Useful first requests are:

- `Buddy, report status.`
- `Buddy, what can you do?`
- `Buddy, navigate to the kitchen.` (only when that named location is
  registered)
- `Buddy, stop.` (deterministic emergency-stop detection remains independent
  of the model)

## Restore high-quality playback

After microphone development, select the headset's A2DP profile again using
the current device/profile IDs:

```bash
pw-cli enum-params DEVICE_ID EnumProfile
wpctl set-profile DEVICE_ID A2DP_PROFILE_INDEX
```

In the tested session, the A2DP profile index was `5`.

## Expected resource behavior

- llama.cpp: three inference threads, no GPU layers, 4096-token context,
  256-token output ceiling, 20-second default timeout;
- whisper.cpp: two threads and a 30-second timeout;
- Piper input: 64 KiB UTF-8 maximum per speech request;
- one dialogue/model request at a time;
- measured Qwen provider peak during the initial live smoke: approximately
  2.4 GiB RSS;
- no audio or model output is retained after provider cleanup.

If a binary, model, audio device, or model response is invalid, the provider
reports diagnostics and fails closed. It does not fabricate a task or bypass
the executive, navigation, arbitration, or safety layers.
