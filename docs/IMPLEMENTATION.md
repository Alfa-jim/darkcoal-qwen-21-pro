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
