import base64
import io
import unittest
from PIL import Image
from worker.request import validate_input
from worker.workflow import build_workflow


def reference(mode='RGBA'):
    stream = io.BytesIO()
    Image.new(mode, (64, 32), (100, 20, 30, 120) if mode == 'RGBA' else (100, 20, 30)).save(stream, format='PNG')
    return {'name': 'picture1', 'image': base64.b64encode(stream.getvalue()).decode()}


class RequestTests(unittest.TestCase):
    def test_defaults_and_resolved_seed(self):
        value = validate_input({'prompt': 'A portrait'})
        self.assertEqual(value['steps'], 40)
        self.assertEqual(value['cfg'], 1)
        self.assertEqual(value['sampler'], 'euler')
        self.assertEqual(value['scheduler'], 'simple')
        self.assertGreaterEqual(value['seed'], 0)
        self.assertLess(value['seed'], 2**53)

    def test_invalid_controls(self):
        for key, value in [('steps', 0), ('steps', True), ('cfg', float('nan')), ('cfg', 11), ('sampler', 'bogus'), ('scheduler', 'bogus'), ('width', 1025), ('reference_resolution', 255), ('seed', -2), ('workflow', {})]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_input({'prompt': 'A portrait', key: value})

    def test_overrides_reach_workflow(self):
        value = validate_input({'prompt': 'Test', 'negative_prompt': 'blur', 'steps': 50, 'cfg': 3, 'sampler': 'heun', 'scheduler': 'karras', 'seed': 42, 'width': 768, 'height': 1024, 'reference_resolution': 1536})
        graph = build_workflow(value, [], 'job')
        self.assertEqual(graph['sample']['inputs']['steps'], 50)
        self.assertEqual(graph['sample']['inputs']['cfg'], 3)
        self.assertEqual(graph['sample']['inputs']['sampler_name'], 'heun')
        self.assertEqual(graph['encode']['inputs']['negative_prompt'], 'blur')
        self.assertEqual(graph['encode']['inputs']['resolution'], 1536)
        self.assertEqual(graph['latent']['inputs']['width'], 768)
        self.assertEqual(graph['sample']['inputs']['denoise'], 1)

    def test_reference_graph_order_and_alpha(self):
        for count in (0, 1, 2, 10):
            refs = [dict(reference(), name=f'picture{i+1}') for i in range(count)]
            value = validate_input({'prompt': 'Test', 'images': refs})
            names = [f'job/ref{i}.png' for i in range(count)]
            graph = build_workflow(value, names, 'job')
            for i in range(count):
                self.assertEqual(graph['encode']['inputs'][f'images.image_{i+1}'], [f'ref{i+1}', 0])
                self.assertEqual(graph[f'ref{i+1}']['class_type'], 'ProLoadReference')
            if count:
                image = Image.open(io.BytesIO(value['images'][0]['bytes']))
                self.assertEqual(image.mode, 'RGBA')
                self.assertEqual(image.getextrema()[3], (120, 120))

    def test_bad_images_and_negative_warning(self):
        with self.assertRaises(ValueError):
            validate_input({'prompt': 'Test', 'images': [dict(reference(), image='bad')]})
        with self.assertRaises(ValueError):
            validate_input({'prompt': 'Test', 'images': [reference()] * 11})
        value = validate_input({'prompt': 'Test', 'negative_prompt': 'blur'})
        self.assertTrue(value['warnings'])


if __name__ == '__main__':
    unittest.main()
