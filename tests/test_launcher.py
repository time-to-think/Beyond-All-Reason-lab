"""Launcher path safety and process cleanup regressions."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('start_duel', ROOT / 'launcher/start_duel.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_probe_timeout_does_not_change_match_config(self):
        bridge_spec = importlib.util.spec_from_file_location('probe_bridge', ROOT / 'agent/bridge.py')
        bridge = importlib.util.module_from_spec(bridge_spec)
        bridge_spec.loader.exec_module(bridge)
        before = (ROOT / 'agent/config.json').read_bytes()
        with patch.object(sys, 'argv', ['bridge.py', '--probe']), patch.object(bridge, 'chat', return_value=({}, {})) as chat, patch.object(bridge.jev, 'require_key'), patch.object(bridge.jev, 'choose', return_value=({}, {})):
            with self.assertRaises(SystemExit) as result:
                bridge.main()
        self.assertEqual(result.exception.code, 0)
        self.assertEqual(chat.call_count, 2)
        for call in chat.call_args_list:
            self.assertEqual(call.args[0]['request_timeout_seconds'], 180)
        self.assertEqual((ROOT / 'agent/config.json').read_bytes(), before)

    def test_rejects_model_startscript_injection(self):
        config = json.loads((ROOT / 'agent/config.json').read_text())
        for value in ('model;deathmode=none;', 'model\nother=1', ''):
            config['local_model'] = value
            with self.assertRaises(ValueError):
                launcher.validate_config(config)

    def test_rejects_bad_limits(self):
        config = json.loads((ROOT / 'agent/config.json').read_text())
        for port in (True, 80, 65536, '18765'):
            with self.assertRaises(ValueError):
                launcher.validate_config(dict(config, port=port))
        for duration in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                launcher.validate_config(dict(config, match_minutes=duration))

    def test_map_configuration_rejects_script_injection(self):
        config = json.loads((ROOT / 'agent/config.json').read_text())
        for name in ('map;deathmode=none;', 'map\nother=1', ''):
            with self.assertRaises(ValueError):
                launcher.validate_config(dict(config, map_name=name))
        for positions in ([[1,2]], [[100,200],[float('nan'),300]], [[100,200],['x',300]]):
            with self.assertRaises(ValueError):
                launcher.validate_config(dict(config, start_positions=positions))

    def test_preparation_and_link_conflict(self):
        with tempfile.TemporaryDirectory(prefix='bar launcher ') as directory:
            base = Path(directory)
            for path in ('data/maps', 'recoil/base', 'recoil/fonts'):
                (base / path).mkdir(parents=True)
            args = ['--prepare-only', '--data-dir', str(base / 'data'), '--engine-dir', str(base / 'recoil'),
                    '--runtime-root', str(base / 'runtime')]
            self.assertEqual(launcher.main(args), 0)
            content = base / 'runtime/content-lab-v3'
            self.assertEqual((content / 'games/BAR.sdd').resolve(), ROOT / 'Beyond-All-Reason')
            script = next((base / 'runtime').glob('*/startscript.txt')).read_text()
            self.assertNotIn('{{', script)
            self.assertIn('GameType=BAR LLM Duel 1;', script)
            wrong = base / 'wrong'
            wrong.mkdir()
            with self.assertRaises(ValueError):
                launcher.link_directory(content / 'maps/installed', wrong)

    def test_does_not_replace_existing_real_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'source').mkdir()
            (base / 'existing').mkdir()
            with self.assertRaises(ValueError):
                launcher.link_directory(base / 'existing', base / 'source')

    def test_posix_link_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'source').mkdir()
            with patch.object(launcher.sys, 'platform', 'linux'), patch.object(Path, 'symlink_to') as link:
                launcher.link_directory(base / 'link', base / 'source')
                link.assert_called_once_with((base / 'source').resolve(), target_is_directory=True)

    def test_owned_child_is_reaped(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            launcher.stop_process(child)
            self.assertIsNotNone(child.poll())
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()


if __name__ == '__main__':
    unittest.main()
