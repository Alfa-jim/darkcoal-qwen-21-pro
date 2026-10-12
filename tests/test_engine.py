import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from PIL import Image
from worker.engine import EngineClient, EngineError
from worker.request import validate_input


class EngineTests(unittest.TestCase):
    def test_completion_preserves_rgba_metadata_and_cleans_files(self):
        with tempfile.TemporaryDirectory() as root:
            client = EngineClient(work_root=root, poll_interval=0)
            def request(method, path, body=None, timeout=30):
                if path == '/prompt':
                    identifier = body['prompt_id']
                    self.assertEqual(body['prompt']['sample']['inputs']['steps'], 50)
                    output = Path(root) / 'output' / identifier / 'image.png'
                    Image.new('RGBA', (256, 256), (1, 2, 3, 128)).save(output)
                    return {'prompt_id': identifier}
                if path.startswith('/history/'):
                    identifier = path.split('/')[-1]
                    return {identifier: {'status': {'completed': True, 'status_str': 'success'}, 'outputs': {'save': {'images': [{'filename': 'image.png', 'subfolder': identifier, 'type': 'output'}]}}}}
                return {}
            client.request = request
            output = client.generate(validate_input({'prompt': 'Test', 'steps': 50, 'width': 256, 'height': 256, 'seed': 42}), 'job')
            self.assertEqual(output['metadata']['seed'], 42)
            self.assertEqual(output['metadata']['settings']['steps'], 50)
            self.assertEqual(output['images'][0]['type'], 'base64')
            self.assertFalse(list((Path(root) / 'output').iterdir()))
            self.assertFalse(list((Path(root) / 'input').iterdir()))

    def test_uncertain_submission_stops_engine_before_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            def abort():
                self.assertTrue(list((Path(root) / 'input').iterdir()))
            callback = Mock(side_effect=abort)
            client = EngineClient(work_root=root, abort=callback)
            client.request = Mock(side_effect=EngineError('lost POST response'))
            with self.assertRaises(EngineError):
                client.generate(validate_input({'prompt': 'Test'}), 'job')
            callback.assert_called_once()
            self.assertFalse(list((Path(root) / 'input').iterdir()))

    def test_output_path_escape_is_rejected_and_process_stopped(self):
        with tempfile.TemporaryDirectory() as root:
            abort = Mock()
            client = EngineClient(work_root=root, abort=abort, poll_interval=0)
            def request(method, path, body=None, timeout=30):
                if path == '/prompt': return {'prompt_id': body['prompt_id']}
                identifier = path.split('/')[-1]
                return {identifier: {'status': {'completed': True}, 'outputs': {'save': {'images': [{'filename': '../../outside.png', 'subfolder': identifier, 'type': 'output'}]}}}}
            client.request = request
            with self.assertRaisesRegex(EngineError, 'escapes'):
                client.generate(validate_input({'prompt': 'Test'}), 'job')
            abort.assert_called_once()

    def test_timeout_stops_engine_and_cleans_job(self):
        with tempfile.TemporaryDirectory() as root:
            abort = Mock()
            client = EngineClient(work_root=root, timeout=.01, poll_interval=0, abort=abort)
            client.request = lambda method,path,body=None,timeout=30: {'prompt_id': body['prompt_id']} if body else {}
            with self.assertRaisesRegex(EngineError, 'timed out'):
                client.generate(validate_input({'prompt': 'Test'}), 'job')
            abort.assert_called_once()


if __name__ == '__main__': unittest.main()
