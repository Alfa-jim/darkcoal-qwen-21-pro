#!/usr/bin/env python3
"""CPU-only node/graph/alpha smoke test with no production weights."""
import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import tempfile

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
COMFY = Path(os.environ.get('COMFYUI_ROOT', '/opt/ComfyUI'))
sys.path.insert(0, str(COMFY))
sys.argv = ['smoke', '--cpu', '--disable-api-nodes', '--disable-metadata']

import comfy.options
comfy.options.enable_args_parsing()
import folder_paths
import nodes
import execution
import torch
from PIL import Image
from worker.engine import check_capabilities
from worker.request import validate_input, SAMPLERS, SCHEDULERS
from worker.workflow import build_workflow, MODEL, ENCODER, VAE


async def main():
    # Initialize the real registered nodes, including the pinned GGUF fork.
    await nodes.init_extra_nodes(init_custom_nodes=True, init_api_nodes=False)
    required = ['UnetLoaderGGUF', 'TextEncodeQwenImage21', 'QwenImage21Cache', 'ProLoadReference']
    for name in required:
        assert name in nodes.NODE_CLASS_MAPPINGS, f'Missing node: {name}'
    import comfy.samplers
    import comfy.sample
    import comfy.latent_formats
    latent_format = comfy.latent_formats.QwenImage21()
    class FakeModel:
        def get_model_object(self, name):
            return latent_format
    latent = nodes.EmptyLatentImage().generate(1024, 768, 1)[0]
    fixed = comfy.sample.fix_empty_latent_channels(FakeModel(), latent['samples'], latent['downscale_ratio_spacial'])
    assert fixed.shape == (1, 64, 48, 64), f'Unexpected Qwen latent shape: {fixed.shape}'
    assert set(SAMPLERS) <= set(comfy.samplers.KSampler.SAMPLERS)
    assert set(SCHEDULERS) <= set(comfy.samplers.KSampler.SCHEDULERS)
    with tempfile.TemporaryDirectory(prefix='qwen-pro-smoke-') as tmp:
        root = Path(tmp)
        folder_paths.set_input_directory(str(root))
        for category, name in [('diffusion_models', MODEL), ('text_encoders', ENCODER), ('vae', VAE)]:
            directory = root / category
            directory.mkdir()
            (directory / name).touch()  # filename/schema validation only; never load these placeholders
            folder_paths.add_model_folder_path(category, str(directory), is_default=True)
        # GGUF folder aliases are registered when imported, so update them to smoke model directories.
        folder_paths.folder_names_and_paths['unet_gguf'] = ([str(root / 'diffusion_models')], {'.gguf'})
        Image.new('RGBA', (32, 32), (10, 20, 30, 128)).save(root / 'alpha.png')
        image = nodes.NODE_CLASS_MAPPINGS['ProLoadReference']().load('alpha.png')[0]
        assert image.shape == (1, 32, 32, 4)
        assert abs(image[0, 0, 0, 3].item() - 128 / 255) < 1e-6
        for count in (0, 1, 2, 10):
            value = validate_input({'prompt': 'CPU schema smoke', 'seed': 42})
            graph = build_workflow(value, ['alpha.png'] * count, 'smoke')
            valid = await execution.validate_prompt('00000000-0000-0000-0000-000000000001', graph, None)
            assert valid[0], f'{count}-reference graph validation failed: {valid}'
    print('CPU smoke passed: Qwen/GGUF nodes, samplers/schedulers, RGBA loader and 0/1/2/10-reference schemas. No GPU inference performed.')


if __name__ == '__main__':
    asyncio.run(main())
