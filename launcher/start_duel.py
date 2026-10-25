"""Portable BAR duel launcher. Requires an installed platform-specific Recoil build."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]


def default_runtime():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'BAR-LLM-Duel'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/BAR-LLM-Duel'
    return Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'bar-llm-duel'


def link_directory(link, target):
    target = target.resolve(strict=True)
    if not target.is_dir():
        raise ValueError(f'Not a directory: {target}')
    if os.path.lexists(link):
        if not (link.is_symlink() or (hasattr(link, 'is_junction') and link.is_junction())):
            raise ValueError(f'Expected a directory link: {link}')
        if link.resolve() != target:
            raise ValueError(f'Content link points elsewhere: {link}. Choose another --runtime-root.')
        return
    link.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == 'win32':
        # Junctions do not require Developer Mode or administrator privileges.
        subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(target)],
                       check=True, stdout=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        link.symlink_to(target, target_is_directory=True)


def validate_config(config):
    if config.get('hybrid_enabled') and config.get('local_council_enabled'):
        raise ValueError('Select local council or JEV hybrid, not both')
    if not isinstance(config.get('map_name', 'Comet Catcher Remake'), str) or not re.fullmatch(r'[A-Za-z0-9_ .-]{1,100}', config.get('map_name', 'Comet Catcher Remake')):
        raise ValueError('Invalid map name')
    if type(config.get('seed', 42)) is not int or not 0 <= config.get('seed', 42) < 2147483648:
        raise ValueError('Invalid seed')
    positions = config.get('start_positions')
    if positions is not None and (not isinstance(positions, list) or len(positions) != 2 or
            any(not isinstance(point, list) or len(point) != 2 or any(type(v) not in (int, float) or not 32 <= v <= 32000 for v in point) for point in positions)):
        raise ValueError('Invalid start positions')
    port = config.get('port')
    duration = config.get('match_minutes')
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Invalid port in config')
    if type(duration) not in (int, float) or not 0 < duration <= 1440:
        raise ValueError('Invalid match duration in config')
    for field in ('local_model', 'cloud_model', *(['jev_model'] if config.get('hybrid_enabled') else [])):
        if not isinstance(config.get(field), str) or not re.fullmatch(r'[A-Za-z0-9_.:/@-]+', config[field]):
            raise ValueError(f'Invalid model name: {field}')

    if config.get('hybrid_enabled') or config.get('local_council_enabled'):
        for field in ('strategy_interval_seconds', 'tactical_interval_seconds',
                      'reaction_interval_seconds', 'tactical_timeout_seconds'):
            value = config.get(field)
            if type(value) not in (int, float) or not 0 < value <= 3600:
                raise ValueError(f'Invalid hybrid timing: {field}')
        for field in ('max_calls_per_team', 'max_strategy_calls', 'command_max_age_frames'):
            value = config.get(field)
            if type(value) is not int or not 1 <= value <= 100000:
                raise ValueError(f'Invalid hybrid limit: {field}')


def stop_process(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('headless', 'hidden', 'mock', 'prepare-only', 'pack-core'):
        parser.add_argument('--' + flag, action='store_true')
    parser.add_argument('--test-seconds', type=int, default=0)
    parser.add_argument('--load-timeout', type=int, default=300,
                        help='Additional wall-clock seconds for test loading (default: 300)')
    parser.add_argument('--config', type=Path, default=ROOT / 'agent/config.json')
    parser.add_argument('--map', choices=('baseline', 'ridge', 'river'))
    parser.add_argument('--swap-starts', action='store_true')
    parser.add_argument('--runtime-root', type=Path, default=default_runtime())
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--engine-dir', type=Path)
    args = parser.parse_args(argv)
    if args.test_seconds < 0:
        parser.error('--test-seconds must be nonnegative')
    if args.load_timeout <= 0:
        parser.error('--load-timeout must be positive')
    settings_path = ROOT / 'launcher/local.json'
    local = json.loads(settings_path.read_text('utf-8-sig')) if settings_path.exists() else {}
    data = (args.data_dir or Path(local.get('data_dir', ROOT.parent / 'BAR-Launcher/data'))).expanduser().resolve()
    engine = (args.engine_dir or Path(local.get('engine_dir', data / 'engine/recoil_2026.07.04'))).expanduser().resolve()
    core = ROOT / 'Beyond-All-Reason'
    if not (core / 'modinfo.lua').is_file():
        raise ValueError('BAR submodule missing. Run git submodule update --init --recursive.')
    executable = engine / ('spring-headless' if args.headless else 'spring')
    if sys.platform == 'win32':
        executable = executable.with_suffix('.exe')
    if not args.prepare_only and not executable.is_file():
        raise ValueError(f'Recoil executable missing: {executable}. Set --engine-dir.')
    config_path = args.config.expanduser().resolve(strict=True)
    config = json.loads(config_path.read_text('utf-8-sig'))
    sys.path.insert(0, str(ROOT / 'maps'))
    from build_maps import build_all, SPECS
    if args.map in SPECS:
        config.update(map_name=SPECS[args.map]['name'], start_positions=SPECS[args.map]['starts'])
    elif args.map == 'baseline':
        config['map_name'] = 'Comet Catcher Remake'
    if args.swap_starts:
        if not config.get('start_positions'):
            raise ValueError('Swapping requires explicit start_positions for this map')
        config['start_positions'] = list(reversed(config['start_positions']))
    validate_config(config)
    if config.get('hybrid_enabled') and not args.mock and not args.prepare_only:
        if not os.environ.get('TYPESAFE_API_KEY', '').strip():
            raise ValueError('JEV key missing. Run Setup-JEV-and-Start.cmd after obtaining a TypeSafe API key.')
    runtime = args.runtime_root.expanduser().resolve()
    if runtime == ROOT or ROOT in runtime.parents:
        raise ValueError('Runtime directory must be outside the source checkout')
    content, cache = runtime / ('content-lab-v3-packed' if args.pack_core else 'content-lab-v3'), runtime / 'cache'
    cache.mkdir(parents=True, exist_ok=True)
    build_all(runtime / 'generated-maps')
    for name, target in {'maps/installed': data / 'maps', 'maps/lab': runtime / 'generated-maps', 'base': engine / 'base', 'fonts': engine / 'fonts',
                         'games/LLMDuel.sdd': ROOT / 'game-extension'}.items():
        link_directory(content / name, target)
    if args.pack_core:
        from pack_core import pack_core
        pack_core(core, content / 'games/BAR.sdz')
    else:
        link_directory(content / 'games/BAR.sdd', core)
    run = runtime / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
    run.mkdir(mode=0o700)
    link_directory(run / 'cache', cache)
    config_path = run / 'config.json'
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    token = secrets.token_hex(32)
    (run / 'session.json').write_text(json.dumps({'token': token, 'test_run': bool(args.test_seconds)}), encoding='utf-8')
    start = (ROOT / 'launcher/startscript.template').read_text('utf-8')
    positions = config.get('start_positions', [[1200,1200],[6800,6800]])
    substitutions = {'MAP_NAME': config.get('map_name', 'Comet Catcher Remake'),
                     'SEED': config.get('seed',42), 'START_TYPE': 3 if config.get('start_positions') else 0,
                     'START_X0': positions[0][0], 'START_Z0': positions[0][1],
                     'START_X1': positions[1][0], 'START_Z1': positions[1][1],
                     'TOKEN': token, 'PORT': config['port'], 'LOCAL_MODEL': config['local_model'],
                     'LOCAL_LABEL': 'Local_Council' if config.get('local_council_enabled') else ('Local_JEV' if config.get('hybrid_enabled') else 'Local'),
                     'CLOUD_MODEL': config['cloud_model'], 'MAX_AGE': config.get('command_max_age_frames', 2700), 'FRAMES': int(config['match_minutes'] * 1800),
                     'DEBUG': f'llm_duel_test_exit=1; debugcommands={args.test_seconds * 30}:quitforce;' if args.test_seconds else ''}
    for key, value in substitutions.items():
        start = start.replace('{{' + key + '}}', str(value))
    (run / 'startscript.txt').write_text(start, encoding='utf-8')
    (run / 'springsettings.cfg').write_text(
        f'SpringData = {content}\nLogFlushLevel = 0\nTCPAllowConnect = 127.0.0.1:{config["port"]}\n'
        'Fullscreen = 0\nXResolutionWindowed = 1280\nYResolutionWindowed = 720\n'
        'VSync = 1\nMaxParticles = 4000\nShadowMapSize = 2048\n', encoding='utf-8')
    print(f'Run directory: {run}', flush=True)
    if args.prepare_only:
        return 0
    bridge_cmd = [sys.executable, str(ROOT / 'agent/bridge.py'), '--config', str(config_path)]
    if not args.mock:
        subprocess.run(bridge_cmd + ['--probe'], check=True)
    bridge_cmd += ['--session', str(run / 'session.json')]
    if args.mock:
        bridge_cmd.append('--mock')
    hidden = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
    bridge = game = None
    try:
        with (run / 'bridge.log').open('w') as out, (run / 'bridge-errors.log').open('w') as err:
            bridge = subprocess.Popen(bridge_cmd, stdout=out, stderr=err, **hidden)
        deadline = time.monotonic() + 10
        while not (run / 'bridge.ready').exists():
            if bridge.poll() is not None:
                raise RuntimeError(f'Bridge failed. Check {run / "bridge-errors.log"}')
            if time.monotonic() >= deadline:
                raise RuntimeError('Bridge readiness timed out')
            time.sleep(0.1)
        command = [str(executable), '--isolation', f'--isolation-dir={content}', f'--write-dir={run}',
                   f'--config={run / "springsettings.cfg"}', str(run / 'startscript.txt')]
        if args.hidden:
            command.append('--hidden')
        with (run / 'engine-console.log').open('w') as out, (run / 'engine-errors.log').open('w') as err:
            game = subprocess.Popen(command, cwd=run, stdout=out, stderr=err,
                                    env={k: v for k, v in os.environ.items() if k != "TYPESAFE_API_KEY"},
                                    **(hidden if args.hidden or args.headless else {}))
        try:
            code = game.wait(timeout=args.test_seconds + args.load_timeout if args.test_seconds else None)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Test exceeded loading/game deadline') from exc
        print(f'Engine exit: {code}')
        return code
    finally:
        stop_process(game)
        stop_process(bridge)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'Launch failed: {error}', file=sys.stderr)
        sys.exit(1)
