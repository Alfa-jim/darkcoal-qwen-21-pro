"""Supervise the private persistent ComfyUI process."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from worker.models import validate_models
from worker.engine import EngineClient, EngineError


class Supervisor:
    def __init__(self):
        self.process = None
        self.volume_root = Path(os.environ.get('MODEL_VOLUME_ROOT', '/runpod-volume'))
        self.root = Path(os.environ.get('WORK_ROOT', '/tmp/qwen-pro')).resolve()
        if self.root == self.volume_root.resolve() or self.root.is_relative_to(self.volume_root.resolve()):
            raise ValueError('WORK_ROOT must be ephemeral and outside the network volume')
        self.start_timeout = float(os.environ.get('ENGINE_START_TIMEOUT', '300'))
        timeout = float(os.environ.get('JOB_TIMEOUT_SECONDS', '1800'))
        self.port = int(os.environ.get('ENGINE_PORT', '8188'))
        if not 1 <= self.port <= 65535 or not math.isfinite(self.start_timeout) or not math.isfinite(timeout) or self.start_timeout <= 0 or timeout <= 0:
            raise ValueError('Invalid engine port or timeout')
        self.client = EngineClient(f'http://127.0.0.1:{self.port}', self.root, timeout, abort=self.stop)

    def ensure_started(self):
        if self.process is not None and self.process.poll() is None:
            return
        if not os.path.ismount(self.volume_root):
            raise RuntimeError('Network volume is not mounted; attach the prepared volume')
        paths = validate_models(self.volume_root, verify_hashes=os.environ.get('VERIFY_MODEL_HASHES') == '1')
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ('input', 'output', 'temp'):
            (self.root / name).mkdir(exist_ok=True)
        config = self.root / 'model_paths.yaml'
        # JSON is valid YAML and safely quotes arbitrary filesystem paths.
        config.write_text(json.dumps({'qwen_pro': {
            'base_path': str(paths['denoiser'].parent.parent), 'is_default': True,
            'diffusion_models': 'diffusion_models', 'text_encoders': 'text_encoders', 'vae': 'vae'}}))
        home = Path(os.environ.get('COMFYUI_ROOT', '/opt/ComfyUI'))
        command = [sys.executable, str(home / 'main.py'), '--listen', '127.0.0.1',
                   '--port', str(self.port), '--disable-auto-launch', '--disable-api-nodes',
                   '--disable-metadata', '--extra-model-paths-config', str(config),
                   '--input-directory', str(self.root / 'input'),
                   '--output-directory', str(self.root / 'output'), '--temp-directory', str(self.root / 'temp')]
        self.process = subprocess.Popen(command, cwd=home)
        deadline = time.monotonic() + self.start_timeout
        try:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(f'ComfyUI exited with code {self.process.returncode}; check preceding logs')
                try:
                    self.client.capabilities()
                    print('Pro engine ready. Models load on the first generation.', flush=True)
                    return
                except EngineError as exc:
                    # Missing nodes are a persistent configuration failure, not a startup wait.
                    if 'missing required' in str(exc) or 'allowlist' in str(exc):
                        raise
                time.sleep(1)
            raise RuntimeError('ComfyUI startup timed out')
        except BaseException:
            self.stop()
            raise

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=15)
            self.process = None
