# darkcoal-qwen-21-pro

Full Qwen Image 2.1 RunPod Serverless worker with configurable generation settings,
using **abenzerps UC Q4_K_M diffusion, INT8 ConvRot Qwen3-VL encoder, BF16 VAE**.
This is independent of `darkcoal-qwen-image-21` Turbo. It accepts text prompts
and up to ten ordered reference pictures, returning base64 PNG plus metadata.

Public image target: `ghcr.io/alfa-jim/darkcoal-qwen-21-pro:latest`.
Publication and GPU validation status are recorded in `docs/VALIDATION.md`.

## Prepare the shared network volume

**Increase your existing 15 GB network volume to at least 40 GB before downloading.**
Turbo remains under `models/qwen-image-21/`. Pro uses `models/qwen-21-pro/` and
does not alter Turbo files. Pro weights total **14,630,866,160 bytes (14.63 GB)**;
both projects together use **25,954,617,896 bytes (25.95 GB)** before small caches.

Use an Ubuntu 24.04 CPU Pod with that NETWORK VOLUME selected at deployment,
normally mounted at `/workspace`. Paste the entire `DOWNLOAD_ON_CPU_POD.sh`
into its terminal, or use the published short command:

```bash
export MODEL_VOLUME_ROOT=/workspace
curl -fL --retry 3 https://raw.githubusercontent.com/Alfa-jim/darkcoal-qwen-21-pro/main/DOWNLOAD_ON_CPU_POD.sh -o /tmp/qwen-pro-models.sh && bash /tmp/qwen-pro-models.sh
```

The bootstrap includes its own installer and pinned manifest. No GPU, PyTorch,
Git clone, HF CLI or login is needed. It checks the mount, resumes partial files,
reports progress about once a second as data arrives, explicitly announces
SHA256 verification, and writes a completion manifest only after verification.
On RunPod's distributed filesystem, `df` reports the backing storage pool rather
than your purchased quota; confirm the 40 GB allocation in the RunPod console.
The downloader populates an attached volume; it does not create or mount one.

Exactly these assets are downloaded from revision
`7959e658915f52274897fb573ffeda49de8dc16b`:

| Component | File | Bytes |
|---|---|---:|
| Diffusion | `diffusion_models/qwen-image-2.1-UC-Q4_K_M.gguf` | 4,604,558,112 |
| Encoder/vision | `text_encoders/qwen3vl_8b_int8_convrot.safetensors` | 9,350,798,360 |
| VAE | `vae/qwen_image_2.1_vae_bf16.safetensors` | 675,509,688 |

Vision is packaged in the encoder; there is no separate mmproj, VL adapter or
prompt enhancer in this setup. This UC model is used directly; the optional LoRA
is not downloaded or applied separately. The release uses the Qwen Research
License. Preserve its terms for your intended deployment.

## Configure RunPod Serverless

| Setting | Starting value |
|---|---|
| Image | `ghcr.io/alfa-jim/darkcoal-qwen-21-pro:latest`, preferably the verified digest |
| GPU | L40S / RTX 6000 Ada **48 GB** |
| Host RAM | **64 GB preferred** |
| CUDA | Compatible with CUDA 12.8 |
| Container disk | **30 GB**; model storage is separate |
| Network volume | Same prepared shared volume, mounted at `/runpod-volume` |
| Active workers | 0 for scale-to-zero, 1 to keep a worker warm |
| Maximum workers | Start with 1 |
| Execution timeout | **2100 seconds** |
| Public HTTP ports | None; ComfyUI is private on localhost |

ComfyUI and the maintained leejet GGUF loader are pinned in Dockerfile. CUDA
Torch/vision and the main Python dependencies are version-pinned; the installed
transitive versions are saved in `/app/installed-requirements.txt` in the image.
The build verifies real Qwen/GGUF nodes, accepted sampler/scheduler values, graph
schemas and alpha-preserving input on CPU without downloading production weights.

Startup checks model sizes/completion manifest, then ComfyUI API readiness before
registering the RunPod handler. **Weights load on the first generation**, then
ComfyUI manages retention and offloading. No runtime weight downloads occur.
Set `VERIFY_MODEL_HASHES=1` for full startup checksum verification (reads 14.63 GB).
Jobs are serialized. Each has private UUID directories on ephemeral disk; input,
output and prompt history are removed after completion. On failures/timeouts the
private engine is terminated before deleting job files, then restarted next job.

Environment options: `MODEL_VOLUME_ROOT=/runpod-volume`, `COMFYUI_ROOT=/opt/ComfyUI`,
`WORK_ROOT=/tmp/qwen-pro`, `ENGINE_PORT=8188`, `ENGINE_START_TIMEOUT=300`,
`JOB_TIMEOUT_SECONDS=1800`. Keep WORK_ROOT outside the network volume.
There is no guarantee that every 2048-pixel/ten-reference workload fits 48 GB;
test your actual workload and lower output/reference resolution if needed.

## Request and response

```json
{"input":{"prompt":"A cinematic portrait","negative_prompt":"","width":1024,"height":1024,"seed":-1,"steps":40,"cfg":1,"sampler":"euler","scheduler":"simple","reference_resolution":1024,"images":[]}}
```

| Input | Default | Validation |
|---|---|---|
| prompt | required | Nonempty text, max 16,384 characters |
| negative_prompt | empty | Max 16,384 characters; inactive when CFG is 1 |
| steps | 40 | Integer 1–100 |
| cfg | 1 | Finite number 1–10 |
| sampler | euler | euler, euler_ancestral, heun, dpmpp_2m |
| scheduler | simple | simple, normal, karras, beta |
| width / height | 1024 | 256–2048, multiples of 32 |
| reference_resolution | 1024 | 256–2048, multiples of 32 |
| seed | −1 | Random replayable 53-bit seed, or explicit signed 64-bit integer |
| images | [] | Up to ten `{name,image}` items: unique names; PNG/JPEG/WebP base64/data URI |

The worker uses ordinary full-model scheduling and denoise 1. It accepts no
arbitrary workflow or filenames. API callers refer to ordered images as
`Picture 1`, `Picture 2`, etc. References may have different dimensions and alpha;
each is limited to 20 MP, combined encoded data to 18 MiB. RunPod's `/run` limit
is lower: the playground uses a conservative 9.5 MB request budget.
Explicit output width/height apply to both text and reference-conditioned modes.
Changing the first reference's aspect ratio can shift edit composition.

Output:

```json
{"images":[{"filename":"<uuid>.png","type":"base64","data":"..."}],"metadata":{"seed":42,"settings":{"steps":40,"cfg":1,"sampler":"euler","scheduler":"simple","width":1024,"height":1024,"reference_resolution":1024,"seed":42,"negative_prompt":""},"generation_seconds":123.45,"warnings":[]}}
```

Seeds beyond JavaScript’s safe integer range are returned as decimal strings in metadata; the browser accepts safe integers only.

Validation/generation errors return `{"error":"message"}` inside RunPod output.
The engine timing includes workflow submission, model loading if cold, and
generation. RunPod reports queue/worker timing separately. More steps/higher CFG
are configurable experiments, not guaranteed quality improvements.

## Personal browser playground

Double-click `OPEN_PLAYGROUND.cmd` on Windows (Python required), or run:

```bash
python -m http.server 8766 --bind 127.0.0.1
```

Open <http://127.0.0.1:8766/playground.html>. Use the same address/browser for
persistent settings. API key, endpoint and sampling fields are saved in local
storage with keys separate from Turbo. The key is masked and removable with
**Forget key**. Use your own local copy/device, not an untrusted hosted copy.

Upload pictures and type `@picture1 is the character. Follow @picture 2's pose.`
Click reference labels or type `@` for suggestions. Mentions become ordered
`Picture N` wording before submission; removed-reference mentions block generation.
Stable labels do not silently renumber after removal. A disclosure previews the
translated prompt. Originals remain in tab memory so increasing reference
resolution reprocesses the originals rather than an already reduced image.
Reference sizing follows Qwen’s area-based resolution (approximately resolution² pixels), preserving aspect ratio; small originals are not upscaled in the browser. Opaque inputs become JPEG; transparency stays PNG. Inputs/results are not stored
across refreshes. Exports include inputs without credentials.

All sampling controls are editable; **Reset to Pro defaults** restores the preset.
Final results show resolved seed/settings, engine time, and any warnings. The live
elapsed timer survives a refresh for a pending job; status resume never submits
another job. Submissions are not automatically retried after network errors.
Use RunPod's Requests tab to check uncertain submissions before trying again.
Async results expire: download the final PNG promptly.

## Validation and development

```bash
python -m pip install Pillow==12.3.0
python -m unittest discover -s tests -v
node --test tests/playground.test.cjs tests/playground-lifecycle.test.cjs
python scripts/make_download_command.py --check
docker build --platform linux/amd64 -t qwen-pro .
docker run --rm --entrypoint python qwen-pro scripts/smoke.py
```

GitHub Actions tests, builds Linux AMD64, runs CPU checks in the final container,
then publishes `latest` and `sha-<full commit>` to GHCR. Run
`python scripts/verify_registry.py` to check anonymous manifests/configs and
record the immutable digest (not a complete image-layer pull).

References: [requested model and setup](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized),
[official text workflow](https://github.com/Comfy-Org/workflow_templates/blob/22323a851441484873668f928663540344a55c35/templates/image_qwen_image_2_1_t2i.json),
[official edit workflow](https://github.com/Comfy-Org/workflow_templates/blob/22323a851441484873668f928663540344a55c35/templates/image_qwen_image_2_1_image_edit.json),
[GGUF loader](https://github.com/leejet/ComfyUI-GGUF/tree/373048b8403a7820620065210a691263d4da0a61),
[RunPod request API](https://docs.runpod.io/serverless/endpoints/send-requests).
