"""API graph distilled from pinned official Qwen 2.1 text/edit workflows."""
from worker.request import DEFAULTS

MODEL = 'qwen-image-2.1-UC-Q4_K_M.gguf'
ENCODER = 'qwen3vl_8b_int8_convrot.safetensors'
VAE = 'qwen_image_2.1_vae_bf16.safetensors'


def build_workflow(value, references, output_prefix):
    def node(kind, **inputs):
        return {'class_type': kind, 'inputs': inputs}
    graph = {
        'model': node('UnetLoaderGGUF', unet_name=MODEL),
        'clip': node('CLIPLoader', clip_name=ENCODER, type='qwen_image', device='default'),
        'vae': node('VAELoader', vae_name=VAE),
        'cache': node('QwenImage21Cache', model=['model', 0], device='auto', dtype='default'),
        'encode': node('TextEncodeQwenImage21', clip=['clip', 0], vae=['vae', 0],
                       prompt=value['prompt'], negative_prompt=value['negative_prompt'],
                       resolution=value['reference_resolution']),
        'latent': node('EmptyLatentImage', width=value['width'], height=value['height'], batch_size=1),
        'sample': node('KSampler', model=['cache', 0], positive=['encode', 0], negative=['encode', 1],
                       latent_image=['latent', 0], seed=value['seed'], steps=value['steps'],
                       cfg=value['cfg'], sampler_name=value['sampler'], scheduler=value['scheduler'], denoise=1.0),
        'decode': node('VAEDecode', samples=['sample', 0], vae=['vae', 0]),
        'save': node('SaveImage', images=['decode', 0], filename_prefix=output_prefix + '/image'),
    }
    for index, name in enumerate(references, 1):
        graph[f'ref{index}'] = node('ProLoadReference', image=name)
        graph['encode']['inputs'][f'images.image_{index}'] = [f'ref{index}', 0]
    return graph


def applied_settings(value):
    settings = {key: value[key] for key in DEFAULTS}
    if value['seed'] > 2**53 - 1:
        settings['seed'] = str(value['seed'])
    return settings
