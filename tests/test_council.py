"""Role separation, scratchpad persistence and mock isolation."""
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from test_hybrid import state
from bridge import CouncilMatch, candidates_for, SYSTEM
from council import Scratchpad, consult


class CouncilTests(unittest.TestCase):
    def test_three_roles_write_and_reuse_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            config = dict(local_model='small', cloud_model='large', local_council_enabled=True,
                          max_calls_per_team=5, strategy_interval_seconds=20, tactical_interval_seconds=0)
            match = CouncilMatch(config, 'test', Path(directory)/'run', mock=True)
            try:
                match.handle(dict(kind='snapshot', token='test', frame=30, teams=[state()]))
                deadline = time.monotonic()+3
                while (match.busy or match.strategy_busy) and time.monotonic()<deadline:
                    time.sleep(.01)
                self.assertEqual({e['role'] for e in match.scratchpad.entries}, {'strategy', 'economy', 'tactical'})
                with patch('bridge.council.consult', return_value=(candidates_for(state())['hold'], {})) as call:
                    match.local_tactics(state(), candidates_for(state()))
                    memory = call.call_args.args[-1]
                    self.assertEqual(len(memory['recent_notes']), 3)
                match.handle(dict(kind='finished', token='test', winner=0, frame=60))
                self.assertFalse(match.scratchpad.history_path.exists())
                self.assertEqual(match.scratchpad.result['local_outcome'], 'win')
            finally:
                match.pool.shutdown(wait=True)

    def test_history_survives_restart_and_includes_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Scratchpad(Path(directory)/'one')
            first.append('strategy', 30, candidates_for(state())['attack_base'], 'Attack after reinforcement.', state())
            first.finish(1, 300, dict(map='fixture', controller='local-council-v1'))
            second = Scratchpad(Path(directory)/'two')
            self.assertEqual(second.context()['completed_matches'][0]['result']['local_outcome'], 'loss')
            self.assertIn('Attack after reinforcement.', json.dumps(second.context()))
            before = second.context()
            third = Scratchpad(Path(directory)/'mock', mock=True)
            self.assertEqual(third.history, [])
            self.assertEqual(second.context(), before)

    def test_history_is_bounded_and_corruption_is_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            pad = Scratchpad(Path(directory)/'run')
            for i in range(65):
                pad.append('tactical', i, candidates_for(state())['hold'], 'Observe.', state())
            self.assertEqual(len(pad.entries), 60)
            pad.history_path.parent.mkdir(exist_ok=True)
            pad.history_path.write_text('broken')
            next_pad = Scratchpad(Path(directory)/'next')
            self.assertTrue(next_pad.load_error)
            self.assertEqual(next_pad.history, [])

    def test_validation_match_does_not_become_experience(self):
        with tempfile.TemporaryDirectory() as directory:
            pad = Scratchpad(Path(directory)/'test', persist=False)
            pad.append('tactical', 30, candidates_for(state())['hold'], 'Observe.', state())
            pad.finish(-1, 900, {})
            self.assertFalse(pad.history_path.exists())
            self.assertEqual(json.loads(pad.path.read_text())['result']['local_outcome'], 'draw')

    def test_cloud_uses_same_choice_contract_without_local_schema(self):
        response = dict(message=dict(content=json.dumps(dict(choice='hold', note='Preserve orders.'))))
        with patch('council.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as call:
            action, _ = consult(dict(ollama_url='http://localhost'), 'gpt-oss:120b-cloud', 'solo',
                                state(), candidates_for(state()), {})
            body = json.loads(call.call_args.args[0].data)
            self.assertNotIn('format', body)
            self.assertNotIn('num_ctx', body['options'])
            self.assertEqual(body['think'], 'low')
            self.assertEqual(action['action'], 'hold')

    def test_role_prompt_schema_and_invalid_choice(self):
        response = dict(model='small', message=dict(content=json.dumps(dict(choice='hold', note='No visible threat.'))))
        with patch('council.urllib.request.urlopen') as open_call:
            open_call.return_value = io.BytesIO(json.dumps(response).encode())
            action, metrics = consult(dict(ollama_url='http://localhost'), 'small', 'economy',
                                      dict(state(), rules=SYSTEM, candidate_actions=candidates_for(state())), candidates_for(state()), {})
            request = json.loads(open_call.call_args.args[0].data)
            self.assertIn('economy specialist', request['messages'][0]['content'])
            supplied_state = json.loads(request['messages'][1]['content'])['state']
            self.assertNotIn('rules', supplied_state)
            self.assertNotIn('candidate_actions', supplied_state)
            self.assertEqual(action['action'], 'hold')
            self.assertEqual(metrics['note'], 'No visible threat.')
            response['message']['content'] = json.dumps(dict(choice='invented', note='Bad.'))
            open_call.return_value = io.BytesIO(json.dumps(response).encode())
            with self.assertRaises(ValueError):
                consult(dict(ollama_url='http://localhost'), 'small', 'tactical', state(), candidates_for(state()), {})


if __name__ == '__main__':
    unittest.main()
