"""Pilot summaries must survive empty armies and Unicode model notes."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'launcher'))
from map_pilot import summarize


class PilotTests(unittest.TestCase):
    def test_empty_ready_army_and_unicode_note(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            teams=[dict(team=t,map='Fixture',map_size=dict(x=8192,z=8192),
                        base=dict(x=.25 if t==0 else .75,z=.5),combat_units=6,
                        factory_alive=True,income_upgrades=0,enemies=[],ready_unit_counts=[],
                        commander=dict(health=100)) for t in (0,1)]
            events=[dict(kind='start',mock=False,config=dict(max_calls_per_team=1)),
                    dict(kind='snapshot',frame=30,teams=teams)]
            for t in (0,1):
                events.append(dict(kind='decision',team=t,frame=30,action=dict(action='attack'),
                                   latency_seconds=.5,note='Advance \u2192 enemy base'))
            events.append(dict(kind='finished',frame=60,winner=1))
            (root/'events.jsonl').write_text('\n'.join(json.dumps(e,ensure_ascii=False) for e in events),encoding='utf-8')
            (root/'infolog.txt').write_text('BAR_DUEL_ACTION team=0 action=attack\nBAR_DUEL_ACTION team=1 action=attack')
            result=summarize(root)
            self.assertTrue(result['audit']['passed'])
            self.assertEqual(result['teams'][0]['max_aircraft'],0)
            self.assertEqual(result['start_positions'],[[2048,4096],[6144,4096]])


if __name__=='__main__':
    unittest.main()
