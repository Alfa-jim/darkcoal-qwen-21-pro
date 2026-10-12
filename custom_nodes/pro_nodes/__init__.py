"""Preserve reference alpha instead of discarding LoadImage's separate mask."""
from pathlib import Path
import numpy as np
import torch
from PIL import Image, ImageOps
import folder_paths


class ProLoadReference:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'image': ('STRING',)}}

    RETURN_TYPES = ('IMAGE',)
    FUNCTION = 'load'
    CATEGORY = 'darkcoal/pro'

    def load(self, image):
        root = Path(folder_paths.get_input_directory()).resolve()
        path = (root / image).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Reference must be inside the private input directory')
        with Image.open(path) as source:
            source.load()
            source = ImageOps.exif_transpose(source)
            pixels = np.array(source.convert('RGBA'), dtype=np.float32) / 255.0
        return (torch.from_numpy(pixels).unsqueeze(0),)

    @classmethod
    def IS_CHANGED(cls, image):
        # Job-specific UUID paths never alias images from other jobs.
        return image


NODE_CLASS_MAPPINGS = {'ProLoadReference': ProLoadReference}
