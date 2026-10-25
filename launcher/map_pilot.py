"""Run a sequential, side-swapped map pilot with isolated cross-match memory."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

from start_duel import ROOT, default_runtime
from verify_run import inspect_run


def summarize(directory):
    events = [json.loads(x) for x in (directory/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    observations = [e for e in events if e['kind']=='snapshot']
    result = next((e for e in events if e['kind']=='finished'), None)
    first = observations[0]['teams'] if observations else []
    last = observations[-1]['teams'] if observations else []
    output = dict(run=str(directory), result=result, teams={}, audit=inspect_run(directory, require_finished=True))
    if first:
        output['map'] = first[0]['map']
        output['start_positions'] = [[round(s['base']['x']*s['map_size']['x']), round(s['base']['z']*s['map_size']['z'])] for s in first]
    for team in (0,1):
        decisions = [e for e in events if e['kind']=='decision' and e['team']==team]
        states = [(e['frame'],s) for e in observations for s in e['teams'] if s['team']==team]
        latencies = sorted(e['latency_seconds'] for e in decisions)
        seen = [f/30 for f,s in states if s['enemies']]
        output['teams'][team] = dict(decisions=len(decisions), actions=dict(Counter(e['action']['action'] for e in decisions)),
            stale=sum(bool(e.get('stale')) for e in decisions),
            p50_seconds=statistics.median(latencies) if latencies else None,
            p95_seconds=latencies[max(0, int(.95*len(latencies)+.999)-1)] if latencies else None,
            first_enemy_seconds=min(seen,default=None),
            max_combat=max((s['combat_units'] for _,s in states),default=0),
            max_aircraft=max((sum(v for k,v in (s['ready_unit_counts'] if isinstance(s['ready_unit_counts'], dict) else {}).items() if k in ('armfig','armthund','armkam','armpeep')) for _,s in states),default=0),
            last_commander_health=next(((s.get('commander') or {}).get('health') for s in last if s['team']==team),None))
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,default=default_runtime().with_name('BAR-LLM-Map-Pilot'))
    parser.add_argument('--resume',type=Path,help='Resume an existing batch without replaying finished cases')
    parser.add_argument('--minutes',type=float,default=3)
    parser.add_argument('--report-dir',type=Path,default=ROOT/'output/map-pilot')
    args=parser.parse_args()
    if not 0 < args.minutes <= 15:
        parser.error('Use a pilot limit between 0 and 15 minutes')
    args.runtime_root.mkdir(parents=True,exist_ok=True)
    # A fresh batch subdirectory prevents previous-match memories from leaking into the pilot.
    batch=args.resume or args.runtime_root/('batch-'+time.strftime('%Y%m%d-%H%M%S'))
    batch.mkdir(exist_ok=bool(args.resume))
    args.report_dir.mkdir(parents=True,exist_ok=True)
    config=json.loads((ROOT/'agent/config.json').read_text())
    config.update(match_minutes=args.minutes,persist_memory=False,seed=42)
    source_paths = [ROOT/'agent/bridge.py',ROOT/'agent/council.py',ROOT/'maps/build_maps.py',
                    ROOT/'game-extension/luarules/gadgets/ai_llm_duel.lua']
    report=dict(protocol={'minutes':args.minutes,'seed':42,'pairing':'physical start swap',
        'memory':'within-match only; no previous matches', 'replicates_per_start':1,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}},runs=[])
    starts={}
    # No concurrent matches: avoid local GPU contention between different games.
    for swapped in (False,True):
        for kind in ('baseline','ridge','river'):
            case=dict(config)
            if kind in starts:
                case['start_positions']=starts[kind]
            case_path=batch/(kind+('-reverse' if swapped else '-forward')+'.json')
            case_path.write_text(json.dumps(case,indent=2))
            command=[sys.executable,str(ROOT/'launcher/start_duel.py'),'--map',kind,'--hidden','--pack-core',
                     '--test-seconds',str(int(args.minutes*60)+10),'--config',str(case_path),
                     '--runtime-root',str(batch)]
            if swapped:
                command.append('--swap-starts')
            case_log=batch/(case_path.stem+'.log')
            existing_run=None
            if args.resume and case_log.exists():
                for line in case_log.read_text(encoding='utf-8',errors='replace').splitlines():
                    if line.startswith('Run directory: '):
                        candidate=Path(line[len('Run directory: '):])
                        event_file=candidate/'events.jsonl'
                        if event_file.exists() and any(json.loads(row).get('kind')=='finished' for row in event_file.read_text(encoding='utf-8').splitlines()):
                            existing_run=candidate
            if existing_run:
                created=[existing_run]
                exit_code=0
                print(json.dumps(dict(status='reusing_completed',map=kind,swapped=swapped)),flush=True)
            else:
                previous={p for p in batch.iterdir() if p.is_dir()}
                print(json.dumps(dict(status='starting',map=kind,swapped=swapped)),flush=True)
                with case_log.open('w') as out:
                    process=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,timeout=int(args.minutes*60)+540)
                exit_code=process.returncode
                created=[p for p in batch.iterdir() if p.is_dir() and p not in previous and (p/'session.json').exists()]
            entry=dict(scenario=kind,swapped=swapped,exit_code=exit_code)
            try:
                if len(created)!=1:
                    raise ValueError('Missing or ambiguous run directory')
                entry.update(summarize(created[0]))
                if not swapped:
                    starts[kind]=entry['start_positions']
                else:
                    entry['swap_verified']=entry['start_positions']==list(reversed(starts[kind]))
            except (OSError,ValueError,KeyError,IndexError) as exc:
                entry['inspection_error']=type(exc).__name__
            report['runs'].append(entry)
            (args.report_dir/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps(dict(status='finished',map=kind,swapped=swapped,
                exit_code=exit_code,result=entry.get('result'),audit_passed=entry.get('audit',{}).get('passed'))),flush=True)
            if exit_code!=0 or 'start_positions' not in entry:
                raise SystemExit('Pilot stopped: inspect the case log before continuing.')
    print('Report: '+str(args.report_dir/'results.json'),flush=True)


if __name__=='__main__':
    main()
