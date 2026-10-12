"""Private ComfyUI API client with per-job filesystem isolation."""
import base64
import io
import json
from pathlib import Path
import shutil
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from PIL import Image
from worker.request import SAMPLERS, SCHEDULERS
from worker.workflow import build_workflow, applied_settings


class EngineError(RuntimeError):
    pass


def check_capabilities(info):
    required = ['UnetLoaderGGUF', 'CLIPLoader', 'VAELoader', 'QwenImage21Cache',
                'TextEncodeQwenImage21', 'EmptyLatentImage', 'KSampler', 'VAEDecode',
                'SaveImage', 'ProLoadReference']
    if any(name not in info for name in required):
        raise EngineError('ComfyUI is missing required Qwen 2.1/GGUF/Pro nodes')
    controls = info['KSampler']['input']['required']
    if not set(SAMPLERS) <= set(controls['sampler_name'][0]) or not set(SCHEDULERS) <= set(controls['scheduler'][0]):
        raise EngineError('Configured sampler/scheduler allowlist is unsupported by this ComfyUI build')


class EngineClient:
    def __init__(self, base_url='http://127.0.0.1:8188', work_root='/tmp/qwen-pro',
                 timeout=1800, poll_interval=.5, abort=None):
        self.base_url = base_url.rstrip('/')
        self.root = Path(work_root)
        self.timeout, self.poll_interval, self.abort = timeout, poll_interval, abort

    def request(self, method, path, body=None, timeout=30):
        raw = json.dumps(body).encode() if body is not None else None
        req = Request(self.base_url + path, data=raw, method=method,
                      headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read(2000).decode(errors='replace')
            raise EngineError(f'ComfyUI HTTP {exc.code}: {detail}') from exc
        except (URLError, OSError, ValueError) as exc:
            raise EngineError(f'ComfyUI unavailable or returned invalid JSON: {exc}') from exc

    def capabilities(self):
        info = self.request('GET', '/object_info')
        check_capabilities(info)
        return info

    def generate(self, value, runpod_job_id):
        identifier = str(uuid.uuid4())
        input_dir = self.root / 'input' / identifier
        output_dir = self.root / 'output' / identifier
        started = time.monotonic()
        deadline = started + self.timeout
        input_dir.mkdir(parents=True, exist_ok=False)
        output_dir.mkdir(parents=True, exist_ok=False)
        try:
            refs = []
            for index, image in enumerate(value['images']):
                name = f'ref{index+1}.png'
                (input_dir / name).write_bytes(image['bytes'])
                refs.append(identifier + '/' + name)
            graph = build_workflow(value, refs, identifier)
            accepted = self.request('POST', '/prompt', {'prompt': graph, 'prompt_id': identifier},
                                    timeout=min(30, self.timeout))
            if accepted.get('prompt_id') != identifier or accepted.get('node_errors'):
                raise EngineError('ComfyUI rejected the generated workflow: ' + str(accepted))
            while time.monotonic() < deadline:
                history = self.request('GET', '/history/' + identifier,
                                       timeout=max(.01, min(30, deadline - time.monotonic())))
                entry = history.get(identifier)
                if entry:
                    status = entry.get('status', {})
                    if status.get('status_str') == 'error':
                        raise EngineError('ComfyUI generation failed: ' + str(status.get('messages', []))[:2500])
                    if status.get('completed'):
                        images = entry.get('outputs', {}).get('save', {}).get('images', [])
                        if len(images) != 1:
                            raise EngineError('ComfyUI completed without exactly one output image')
                        image = images[0]
                        path = (self.root / 'output' / image.get('subfolder', '') / image.get('filename', '')).resolve()
                        if image.get('type') != 'output' or not path.is_relative_to(output_dir.resolve()):
                            raise EngineError('Output image path escapes its isolated job directory')
                        raw = path.read_bytes()
                        with Image.open(io.BytesIO(raw)) as decoded:
                            if decoded.format != 'PNG' or decoded.size != (value['width'], value['height']):
                                raise EngineError('ComfyUI output format or dimensions differ from the request')
                            decoded.load()
                        result = {'images': [{'filename': identifier + '.png', 'type': 'base64',
                                               'data': base64.b64encode(raw).decode()}],
                                  'metadata': {'seed': value['seed'] if value['seed'] <= 2**53 - 1 else str(value['seed']), 'settings': applied_settings(value),
                                               'generation_seconds': round(time.monotonic() - started, 3),
                                               'warnings': value['warnings']}}
                        self.request('POST', '/history', {'delete': [identifier]})
                        return result
                time.sleep(min(self.poll_interval, max(0, deadline - time.monotonic())))
            raise EngineError(f'Generation timed out after {self.timeout:g} seconds')
        except BaseException:
            # Stop the sole private process before deleting files it could still write.
            if self.abort:
                self.abort()
            raise
        finally:
            shutil.rmtree(input_dir, ignore_errors=True)
            shutil.rmtree(output_dir, ignore_errors=True)
