import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from worker.runtime import Supervisor
from worker.engine import EngineError
import handler


class RuntimeTests(unittest.TestCase):
    def test_work_directory_cannot_enter_model_volume(self):
        with patch.dict(os.environ, {'MODEL_VOLUME_ROOT': '/volume', 'WORK_ROOT': '/volume/jobs'}):
            with self.assertRaisesRegex(ValueError, 'outside'):
                Supervisor()

    def test_timeout_must_be_finite(self):
        for name, value in [('JOB_TIMEOUT_SECONDS', 'nan'), ('ENGINE_START_TIMEOUT', 'inf')]:
            with patch.dict(os.environ, {name: value}), self.assertRaises(ValueError):
                Supervisor()

    def test_handler_stops_failed_engine_and_next_job_restarts(self):
        supervisor = Mock()
        supervisor.client.generate.side_effect = [EngineError('lost response'), {'images': [], 'metadata': {'seed': 42}}]
        with patch.object(handler, '_supervisor', supervisor):
            self.assertIn('error', handler.handler({'input': {'prompt': 'Test'}}))
            self.assertIn('metadata', handler.handler({'input': {'prompt': 'Test', 'seed': 42}}))
        supervisor.stop.assert_called_once()
        self.assertEqual(supervisor.ensure_started.call_count, 2)

    def test_invalid_request_does_not_start_engine(self):
        with patch.object(handler, '_supervisor', None), patch.object(handler, 'Supervisor') as factory:
            self.assertIn('error', handler.handler({'input': {'prompt': 'Test', 'steps': 101}}))
            factory.assert_not_called()


if __name__ == '__main__': unittest.main()
