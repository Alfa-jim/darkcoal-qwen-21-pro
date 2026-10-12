# Pro implementation ledger

Approved scope: separate public Alfa-jim/darkcoal-qwen-21-pro project and image,
ComfyUI plus leejet GGUF loader, Q4_K_M/INT8 encoder/BF16 VAE, shared 40 GB
volume, configurable sampling, direct prompts, 48 GB GPUs, isolated jobs and Pro
playground. Existing Turbo files must not change.

Stages: request/workflow tests; worker/runtime; pinned installer; playground;
CPU container validation; whole-project review; public repo/image publication.

Ruling: upstream LoadImage separates alpha from RGB. Provide a narrow local
reference loader returning RGBA so TextEncodeQwenImage21 receives alpha intact.
Use standard SaveImage, which saves all decoded image channels without stripping alpha.

Ruling: ComfyUI API readiness and model validation precede SDK registration;
weights load on the first generation, then ComfyUI manages retention/offloading.
Do not represent CPU smoke checks as CUDA inference tests.

Review fixes: generate browser-safe random seeds, stringify explicit larger
seeds in metadata, and resize references by Qwen's target pixel area, not longest
edge. A tensor CPU smoke asserts automatic latent-channel/spatial conversion.

Ruling: switch Pro from CUDA 12.8 to a pinned CUDA 13.0.2 base and Torch cu130.
Pinned comfy/quant_ops.py explicitly disables the optimized CUDA backend below
13.0, affecting the selected INT8 ConvRot encoder. Verified official image and
wheel availability. Cost: RunPod workers require R580+ drivers/CUDA 13 support.
The Turbo image is unchanged.

Smoke harness follows main.py's server/asset-manager initialization order before
node registration, eliminating an unrelated node-replacement import warning.
