"""Hybrid concurrency, response validation, and shared action contract tests."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))
from bridge import HybridMatch, candidates_for
import jev


def state(team=0):
    return dict(team=team, metal=1500, income_upgrades=0, combat_units=6,
                factory_alive=True, air_factory_alive=True, queued_total=0, air_queued_total=0,
                base=dict(x=.2, z=.2), enemy_base=dict(x=.8, z=.8), enemies=[],
                commander=dict(x=.2, z=.2, health=100, max_health=100))


class HybridTests(unittest.TestCase):
    def make_match(self, **changes):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = dict(local_model='local', cloud_model='cloud', max_calls_per_team=5,
                      strategy_interval_seconds=20, tactical_interval_seconds=3,
                      reaction_interval_seconds=1, command_max_age_frames=150)
        config.update(changes)
        match = HybridMatch(config, 'test', Path(directory.name), mock=True)
        self.addCleanup(match.pool.shutdown, wait=True)
        return match

    def send(self, match, frame, states):
        return match.handle(dict(kind='snapshot', token='test', frame=frame, teams=states))

    def wait(self, match):
        deadline = time.monotonic()+3
        while (match.busy or match.strategy_busy) and time.monotonic()<deadline:
            time.sleep(.005)
        self.assertFalse(match.busy or match.strategy_busy)

    def test_slow_strategy_does_not_block_tactics_or_execute_itself(self):
        match = self.make_match()
        match.mock = False
        entered, release = threading.Event(), threading.Event()
        def slow(*args):
            entered.set()
            release.wait(2)
            return candidates_for(state())['economy'], {}
        with patch('bridge.chat', side_effect=slow), patch('bridge.jev.choose', return_value=(candidates_for(state())['defend'], {})):
            self.send(match, 30, [state()])
            self.assertTrue(entered.wait(1))
            deadline = time.monotonic()+1
            while match.busy and time.monotonic()<deadline:
                time.sleep(.005)
            self.assertEqual(match.pending[0]['action'], 'defend')
            self.assertTrue(match.strategy_busy)
            release.set()
            self.wait(match)
        self.assertEqual(len(match.pending), 1)
        self.assertEqual(match.strategy['action'], 'economy')

    def test_threat_bypasses_normal_interval_for_both_sides(self):
        match = self.make_match(tactical_interval_seconds=100, reaction_interval_seconds=0)
        self.send(match, 30, [state(0), state(1)])
        self.wait(match)
        self.send(match, 60, [state(0), state(1)])
        self.assertEqual(match.calls, {0: 1, 1: 1})
        attacked = [dict(state(t), enemies=[dict(id=99, x=.25, z=.25)]) for t in (0, 1)]
        self.send(match, 90, attacked)
        self.wait(match)
        self.assertEqual(match.calls, {0: 2, 1: 2})

    def test_changed_threat_discards_inflight_order(self):
        match = self.make_match(max_strategy_calls=0)
        match.mock = False
        entered, release = threading.Event(), threading.Event()
        def slow(*args):
            entered.set()
            release.wait(2)
            return candidates_for(state())['attack_base'], {}
        with patch('bridge.jev.choose', side_effect=slow):
            self.send(match, 30, [state()])
            self.assertTrue(entered.wait(1))
            self.send(match, 60, [dict(state(), enemies=[dict(id=3, x=.3, z=.3)])])
            release.set()
            self.wait(match)
        self.assertEqual(match.pending, [])
        self.assertTrue(match.urgent[0])

    def test_budget_and_finish(self):
        match = self.make_match(max_calls_per_team=1, max_strategy_calls=1, tactical_interval_seconds=0)
        self.send(match, 30, [state()])
        self.wait(match)
        self.send(match, 60, [state()])
        self.wait(match)
        self.assertEqual(match.calls[0], 1)
        self.assertEqual(match.strategy_calls, 1)
        match.handle(dict(kind='finished', token='test', frame=60, winner=-1))
        self.assertEqual(match.pending, [])

    def test_invalid_choice_has_no_silent_fallback(self):
        match = self.make_match(max_strategy_calls=0)
        match.mock = False
        with patch('bridge.jev.choose', side_effect=TimeoutError('secret-response')):
            self.send(match, 30, [state()])
            self.wait(match)
        self.assertEqual(match.pending, [])
        self.assertNotIn('secret-response', match.log_path.read_text())

    def test_candidates_respect_factories_and_queue_caps(self):
        choices = candidates_for(dict(state(), factory_alive=False, air_queued_total=9, metal=0))
        self.assertFalse(any(k.startswith('produce') for k in choices))
        self.assertNotIn('economy', choices)
        self.assertIn('retreat', choices)
        self.assertIn('hold', choices)


class JevTests(unittest.TestCase):
    def test_missing_key_and_unknown_choice(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                jev.require_key()
        with patch.dict(os.environ, TYPESAFE_API_KEY='fixture-key'), patch('jev.urllib.request.build_opener') as opener:
            response = dict(model='fixture', answers=dict(action=dict(type='choice', choice='unknown')))
            opener.return_value.open.return_value = io.BytesIO(json.dumps(response).encode())
            with self.assertRaises(ValueError):
                jev.choose({}, state(), candidates_for(state()))

    def test_official_contract_and_credentials_not_in_body(self):
        with patch.dict(os.environ, TYPESAFE_API_KEY='fixture-key'), patch('jev.urllib.request.build_opener') as opener:
            response = dict(model='fixture', answers=dict(action=dict(type='choice', choice='defend', confidence=.8)),
                            usage=dict(input_tokens=100, output_tokens=5))
            opener.return_value.open.return_value = io.BytesIO(json.dumps(response).encode())
            action, metrics = jev.choose({}, state(), candidates_for(state()))
            request = opener.return_value.open.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual(request.full_url, 'https://api.typesafe.ai/v1/systemone')
            self.assertEqual(request.headers['Authorization'], 'Bearer fixture-key')
            self.assertEqual(body['questions']['action']['type'], 'choice')
            self.assertNotIn('fixture-key', request.data.decode())
            self.assertEqual(action['action'], 'defend')
            self.assertEqual(metrics['usage']['input_tokens'], 100)


if __name__ == '__main__':
    unittest.main()
