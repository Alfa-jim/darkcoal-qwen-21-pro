"""Validate the bounded public Pro API without importing GPU libraries."""
import base64
import binascii
import io
import math
import secrets
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError

SAMPLERS = ('euler', 'euler_ancestral', 'heun', 'dpmpp_2m')
SCHEDULERS = ('simple', 'normal', 'karras', 'beta')
DEFAULTS = dict(width=1024, height=1024, steps=40, cfg=1.0, sampler='euler',
                scheduler='simple', seed=-1, negative_prompt='', reference_resolution=1024)


def validate_input(value):
    if not isinstance(value, dict):
        raise ValueError('input must be an object')
    unknown = set(value) - set(DEFAULTS) - {'prompt', 'images'}
    if unknown:
        raise ValueError('Unsupported input fields: ' + ', '.join(sorted(unknown)))
    result = dict(DEFAULTS, **value)
    for name in ('prompt', 'negative_prompt'):
        text = result.get(name)
        if not isinstance(text, str) or len(text) > 16384 or (name == 'prompt' and not text.strip()):
            raise ValueError(f'{name} must be text of at most 16,384 characters; prompt cannot be empty')
    for name in ('width', 'height', 'reference_resolution'):
        n = result[name]
        if type(n) is not int or not 256 <= n <= 2048 or n % 32:
            raise ValueError(f'{name} must be 256–2048 and divisible by 32')
    if type(result['steps']) is not int or not 1 <= result['steps'] <= 100:
        raise ValueError('steps must be an integer from 1 to 100')
    cfg = result['cfg']
    if type(cfg) not in (int, float) or not math.isfinite(cfg) or not 1 <= cfg <= 10:
        raise ValueError('cfg must be a finite number from 1 to 10')
    if result['sampler'] not in SAMPLERS or result['scheduler'] not in SCHEDULERS:
        raise ValueError('Unsupported sampler or scheduler')
    seed = result['seed']
    if type(seed) is not int or not -1 <= seed <= 2**63 - 1:
        raise ValueError('seed must be -1 or a nonnegative signed 64-bit integer')
    # Default random seeds must remain exactly replayable in browser JSON/Number.
    result['seed'] = secrets.randbelow(2**53) if seed == -1 else seed
    refs = result.get('images', [])
    if not isinstance(refs, list) or len(refs) > 10:
        raise ValueError('images must be a list of at most 10 references')
    decoded, names, total = [], set(), 0
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict):
            raise ValueError(f'images[{index}] must contain name and image')
        name, encoded = ref.get('name'), ref.get('image')
        if not isinstance(name, str) or not name or len(name) > 255 or name in names:
            raise ValueError('Reference names must be nonempty and unique (max 255 characters)')
        names.add(name)
        if not isinstance(encoded, str) or not encoded:
            raise ValueError('Reference image must be base64 or an image data URI')
        if encoded.startswith('data:'):
            prefix, sep, encoded = encoded.partition(',')
            if not sep or not prefix.startswith('data:image/') or not prefix.endswith(';base64'):
                raise ValueError('Invalid image data URI')
        total += len(encoded)
        if total > 18 * 1024 * 1024:
            raise ValueError('Encoded references exceed 18 MiB; compress or resize them')
        try:
            raw = base64.b64decode(encoded, validate=True)
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format not in ('PNG', 'JPEG', 'WEBP') or image.width * image.height > 20_000_000:
                        raise ValueError('References must be PNG/JPEG/WebP, at most 20 megapixels')
                    image.load()
                    image = ImageOps.exif_transpose(image)
                    image = image.convert('RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB')
                    stream = io.BytesIO()
                    image.save(stream, format='PNG')
                    decoded.append({'name': name, 'bytes': stream.getvalue()})
        except (binascii.Error, OSError, UnidentifiedImageError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as exc:
            raise ValueError(f'images[{index}] is not a valid supported image') from exc
    result['images'] = decoded
    result['warnings'] = ['Negative prompt is inactive at CFG 1.'] if cfg == 1 and result['negative_prompt'].strip() else []
    return result
