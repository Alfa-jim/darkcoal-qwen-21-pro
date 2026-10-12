# Validation status

Local and Linux CI verification: **26 Python tests and 18 Node tests pass**,
including compilation and bootstrap checks. The cleanup fix adds two transport
regressions. Its Linux AMD64 build, final-runtime CPU smoke and publication passed:
https://github.com/Alfa-jim/darkcoal-qwen-21-pro/actions/runs/38235279279

Fixed public image:
`ghcr.io/alfa-jim/darkcoal-qwen-21-pro@sha256:5494dea99f4dde6de79ac7114b40ada5f7cd718f53b109823db46a0512e409c3`
Verified anonymous access by commit tag, digest and latest; latest matches the
fixed commit-tag digest. Compressed layer bytes: 5,522,347,915 (5.52 GB).
No production model files have been downloaded locally. No paid GPU generation
has been run and no RunPod resources have been created by this task.

Verified:

- Public pinned Hugging Face URLs return HTTP 200 and the exact three manifest
  sizes, using HEAD requests without downloading the model bodies.
- Browser URL: `http://127.0.0.1:8766/playground.html`. Fake credentials and changed
  steps/CFG/sampler/scheduler/negative prompt survived a reload. Reset restores
  Pro defaults; fake credentials were removed afterwards.
- Two PNG test references and space-tolerant prompt mentions exported into the
  actual worker input contract, with no key or endpoint in the JSON payload.
- A 2048×1024 source at resolution 1024 became 1440×736; its portrait transparent
  counterpart became 736×1440 with RGBA preserved. At resolution 2048, both were
  reprocessed from originals and retained their original 2048×1024 / 1024×2048
  dimensions. Missing-reference mentions blocked submission before API calls.
- A separate browser tab at mobile width had content/client widths both 375 px
  under the 390×844 viewport override. Desktop layout was inspected. Browser
  console had no warnings/errors. Screenshot is ignored `.validation/playground.jpg`.
- Fresh whole-project review identified seed precision and reference sizing
  issues; both are fixed with regressions. Source inspection confirmed empty
  latent channel and spatial conversion, now protected by a CPU tensor smoke.

The first Linux check caught a CRLF-embedded manifest mismatch in the generated
bootstrap. Normalizing it to LF fixed the check. The CUDA 12.8 diagnostic build
passed required node/alpha/graph/tensor smoke, but exposed a backend warning:
the pinned ComfyUI disables optimized CUDA quantized operations below CUDA 13.
Production uses pinned CUDA 13.0.2/Torch cu130 and a complete server initialization
order in smoke. Initial CUDA 13 build succeeded:
https://github.com/Alfa-jim/darkcoal-qwen-21-pro/actions/runs/38229140256
Both build-time and final-runtime CPU smoke passed. Initial digest
`sha256:2fa79b1e82bd20541e1921c9764e15990ed71cf6af7fb66c1e78931e04103f2b`
was publicly accessible by latest, commit tag, digest, and Docker's anonymous
manifest authentication flow. It contains the cleanup bug described below and
must be replaced with the fixed image above, followed by worker redeployment.

User-reported first generation reached ComfyUI completion but returned a worker
JSON error. Root cause: pinned POST /history returns HTTP 200 with an empty body;
the transport incorrectly decoded it as JSON after successfully reading the PNG.
The regression reproduces the real request/response sequence and failed with the
same JSON error before the fix. The client now accepts an empty acknowledgment
only for POST /history; JSON-bearing endpoints still reject empty responses.
The completed image returns normally and per-job cleanup still runs. A rebuild
is required; a playground refresh alone cannot fix old worker containers.

Mocked job tests cover success, uncertain submission, output-path escapes,
timeouts, process recycling, per-job cleanup, and request rejection before
startup. Browser lifecycle tests use mocked RunPod responses and are not live
GPU-generation evidence. Seeds larger than safe JS integers remain supported by
the API and are encoded as strings in returned metadata; default random seeds
are safe integers for exact browser replay.

GPU acceptance requires the configured endpoint and prepared shared volume:
text-only 1024px generation; two-reference composition with alpha; overridden
steps/CFG/sampler; requested transparent PNG; ten-reference memory check; then a
second warm-worker job. Measure timings and inspect output rather than treating
CPU tests as output-quality validation.
