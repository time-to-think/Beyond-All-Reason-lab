"""Loopback-only BAR strategy bridge. No third party Python dependencies.

Models choose macro actions; identical Lua execution rules handle both sides.
Ollama's authenticated daemon handles cloud credentials, never game scripts.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import secrets
import socket
import socketserver
import threading
import time
import urllib.error
import urllib.request
import jev
import council

ROOT = Path(__file__).resolve().parent
SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["produce", "attack", "defend", "economy", "retreat", "hold"]},
        "unit": {"type": "string", "enum": ["light", "heavy", "scout", "antiair", "fighter", "bomber", "gunship", "airscout"]},
        "count": {"type": "integer", "minimum": 1, "maximum": 3},
        "x": {"type": "number", "minimum": 0, "maximum": 1},
        "z": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["action", "unit", "count", "x", "z"],
    "additionalProperties": False,
}
SYSTEM = """You control one side in a Beyond All Reason strategy duel.
Return ONLY one JSON object: action (produce/attack/defend/economy/retreat/hold),
unit (light/heavy/scout/antiair/fighter/bomber/gunship/airscout), count (1..3),
x and z (normalized map coordinates 0..1).
Include all five fields for every action, even when unused. For example:
{"action":"economy","unit":"light","count":1,"x":0.5,"z":0.5}
Both players have identical rules and limited vision. Enemy_base is public starting
position, not live intelligence. Enemy units contain only line-of-sight observations.
produce queues 1..3 units at the appropriate factory: vehicle factory has
light=armflash, heavy=armstump, scout=armfav, antiair=armsam; aircraft factory has
fighter=armfig (anti-air), bomber=armthund (ground bombing), gunship=armkam
(ground attack), airscout=armpeep (unarmed reconnaissance). Both factories are
available from the start; each has a queue limit of 9. Aircraft cost real resources.
attack sends all controlled ground and air units to x,z using fight.
defend regroups all controlled units around your own base. economy spends 300 metal for +3
metal and +30 energy income per second, at most 5 upgrades. Start with both factories,
commander, 6 light tanks, 1500 metal and 10000 energy. Base bonus income 15 metal
and 150 energy/sec. Factory loss cannot be repaired in this bounded demo.
retreat moves the commander and army to x,z using MOVE. hold preserves current orders.
When candidate_actions is present, copy exactly one offered action object.
When role is strategy, return an advisory action objective for the next 20 seconds; it is not executed directly.
Win by destroying the opposing commander. Balance production, economy, and attacks.
Avoid endlessly investing or producing without attacking. Do not invent other actions.
"""


def validate_action(value):
    if not isinstance(value, dict) or set(value) != set(SCHEMA["required"]):
        raise ValueError("Invalid action fields")
    if value["action"] not in SCHEMA["properties"]["action"]["enum"]:
        raise ValueError("Invalid action")
    if value["unit"] not in SCHEMA["properties"]["unit"]["enum"]:
        raise ValueError("Invalid unit")
    if type(value["count"]) is not int or not 1 <= value["count"] <= 3:
        raise ValueError("Invalid count")
    for key in ("x", "z"):
        if type(value[key]) not in (int, float) or not math.isfinite(value[key]) or not 0 <= value[key] <= 1:
            raise ValueError("Invalid position")
    return value


def chat(config, model, state):
    cloud = model.endswith("cloud")
    body = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": json.dumps(state, ensure_ascii=False)}],
        "stream": False,
        "think": "low" if model.startswith("gpt-oss") else False,
        "options": {"temperature": 0.2, "num_predict": config["max_output_tokens"]},
        "keep_alive": "10m",
    }
    # Ollama Cloud does not guarantee schema-constrained generation.
    if not cloud:
        body["format"] = SCHEMA
        body["options"]["num_ctx"] = config["local_context"]
    request = urllib.request.Request(config["ollama_url"] + "/api/chat",
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=config["request_timeout_seconds"]) as response:
        result = json.load(response)
    content = result["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    action = validate_action(json.loads(content))
    return action, {"latency_seconds": round(time.monotonic() - start, 3),
                    "eval_count": result.get("eval_count"),
                    "prompt_eval_count": result.get("prompt_eval_count"),
                    "reported_model": result.get("model")}


class Match:
    def __init__(self, config, token, log_dir, mock=False):
        self.config, self.token, self.mock = config, token, mock
        self.models = {0: config["local_model"], 1: config["cloud_model"]}
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.busy = set()
        self.calls = {0: 0, 1: 0}
        self.last = {0: -1e10, 1: -1e10}
        self.pending = []
        self.finished = False
        self.latest_frame = -1
        self.log_path = log_dir / "events.jsonl"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log("start", models=self.models, config=config, mock=mock)

    def log(self, kind, **fields):
        record = {"time": datetime.now(timezone.utc).isoformat(), "kind": kind, **fields}
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def handle(self, message):
        if not isinstance(message, dict):
            return {"error": "invalid message"}
        supplied_token = message.get("token", "")
        if not isinstance(supplied_token, str) or not secrets.compare_digest(
                supplied_token.encode(), self.token.encode()):
            return {"error": "unauthorized"}
        with self.lock:
            if message.get("kind") == "snapshot" and not self.finished:
                frame = message.get("frame")
                if type(frame) is not int or frame < 0 or frame <= self.latest_frame:
                    return {"error": "stale frame"}
                states = message.get("teams", [])
                if (not isinstance(states, list) or len(states) > 2
                        or any(not isinstance(state, dict) or type(state.get("team")) is not int
                               or state["team"] not in self.models for state in states)
                        or len({state["team"] for state in states}) != len(states)):
                    return {"error": "invalid teams"}
                self.latest_frame = frame
                self.log("snapshot", frame=frame, teams=states)
                for state in states:
                    team = state.get("team")
                    if type(team) is not int or team not in self.models:
                        continue
                    self.schedule(team, frame, state)
            elif message.get("kind") == "finished":
                if (type(message.get("winner")) is not int or message["winner"] not in (-1, 0, 1)
                        or type(message.get("frame")) is not int
                        or message["frame"] < self.latest_frame):
                    return {"error": "invalid result"}
                if not self.finished:
                    self.log("finished", winner=message.get("winner"), frame=message.get("frame"))
                self.finished = True
                self.pending.clear()
            elif message.get("kind") not in ("poll", "snapshot"):
                return {"error": "invalid kind"}
            commands = [c for c in self.pending if self.latest_frame - c["frame"] <= self.config.get("command_max_age_frames", 2700)]
            self.pending = []
            return {"commands": commands, "calls": dict(self.calls), "finished": self.finished}

    def schedule(self, team, frame, state):
        now = time.monotonic()
        if (team not in self.busy and self.calls[team] < self.config["max_calls_per_team"]
                and now - self.last[team] >= self.config["decision_interval_seconds"]):
            self.busy.add(team)
            self.calls[team] += 1
            self.last[team] = now
            self.pool.submit(self.decide, team, frame, state)

    def decide(self, team, frame, state):
        try:
            if self.mock:
                action = dict(action="attack", unit="light", count=1,
                              x=state["enemy_base"]["x"], z=state["enemy_base"]["z"])
                if self.config.get("mock_scenario") == "air":
                    sequence = ["fighter", "bomber", "gunship", "airscout", "antiair"]
                    index = self.calls[team] - 1
                    if index < len(sequence):
                        action.update(action="produce", unit=sequence[index])
                metrics = {"latency_seconds": 0, "mock": True}
            else:
                action, metrics = chat(self.config, self.models[team], state)
            with self.lock:
                # Do not execute decisions from an obsolete battlefield state.
                stale = self.latest_frame - frame > 2700
                self.log("decision", team=team, frame=frame, model=self.models[team],
                         action=action, stale=stale, **metrics)
                if not self.finished and not stale:
                    self.pending.append({"team": team, "frame": frame, **action})
        except Exception as exc:
            # Never log arbitrary HTTP bodies, headers, or credentials.
            with self.lock:
                self.log("error", team=team, frame=frame, error_type=type(exc).__name__,
                         status=getattr(exc, "code", None),
                         validation=str(exc) if type(exc) is ValueError and str(exc) in
                         {"Invalid action fields", "Invalid action", "Invalid unit", "Invalid count", "Invalid position"}
                         else None)
        finally:
            with self.lock:
                self.busy.discard(team)


def candidates_for(state):
    """Identical bounded actions for both controllers; Lua rechecks live state."""
    base = state.get("base", {"x": .5, "z": .5})
    enemy = state.get("enemy_base", {"x": .8, "z": .8})
    def action(name, point=base, unit="light"):
        return dict(action=name, unit=unit, count=1, x=point["x"], z=point["z"])
    choices = {"hold": action("hold"), "defend": action("defend"),
               "attack_base": action("attack", enemy)}
    commander = state.get("commander")
    if commander:
        # A short step away from observed enemies, or toward home if none are visible.
        enemies = state.get("enemies", [])
        target = base
        if enemies:
            threat = min(enemies, key=lambda e: (e['x']-commander['x'])**2 + (e['z']-commander['z'])**2)
            dx, dz = commander['x']-threat['x'], commander['z']-threat['z']
            length = max(math.hypot(dx, dz), .001)
            target = {"x": max(.01, min(.99, commander['x']+.06*dx/length)),
                      "z": max(.01, min(.99, commander['z']+.06*dz/length))}
        choices['retreat'] = action('retreat', target)
    if state.get('metal', 0) >= 300 and state.get('income_upgrades', 0) < 5:
        choices['economy'] = action('economy')
    if state.get('combat_units', 0) < 100:
        for unit in SCHEMA['properties']['unit']['enum']:
            air = unit in ('fighter', 'bomber', 'gunship', 'airscout')
            prefix = 'air_' if air else ''
            if state.get(prefix+'factory_alive') and state.get(prefix+'queued_total', 0) < 9:
                choices['produce_'+unit] = action('produce', unit=unit)
    return choices


def threat_changed(previous, current):
    if previous is None:
        return False
    old = {e.get('id') for e in previous.get('enemies', [])}
    new = {e.get('id') for e in current.get('enemies', [])}
    old_hp = (previous.get('commander') or {}).get('health', 0)
    new_hp = (current.get('commander') or {}).get('health', old_hp)
    max_hp = max((current.get('commander') or {}).get('max_health', 1), 1)
    # Trigger on first damage or a health-band transition, not every damage tick.
    # Otherwise a continuous fight would invalidate every network response.
    damaged = new_hp < old_hp and (old_hp >= max_hp or int(new_hp/max_hp*4) < int(old_hp/max_hp*4))
    return bool(new-old) or damaged


class HybridMatch(Match):
    """Independent strategic and tactical workers; only tactical choices issue commands."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool.shutdown()
        self.pool = ThreadPoolExecutor(max_workers=3)
        self.states = {}
        self.strategy = None
        self.strategy_frame = -1
        self.strategy_busy = False
        self.strategy_last = -1e10
        self.strategy_calls = 0
        self.urgent = {0: False, 1: False}
        self.epoch = {0: 0, 1: 0}
        self.previous_action = {0: None, 1: None}

    def schedule(self, team, frame, state):
        now = time.monotonic()
        if threat_changed(self.states.get(team), state):
            self.urgent[team] = True
            self.epoch[team] += 1
            self.pending = [c for c in self.pending if c['team'] != team]
        self.states[team] = state
        if (team == 0 and not self.strategy_busy
                and self.strategy_calls < self.config.get('max_strategy_calls', 45)
                and now-self.strategy_last >= self.config.get('strategy_interval_seconds', 20)):
            self.strategy_busy = True
            self.strategy_last = now
            self.strategy_calls += 1
            self.pool.submit(self.plan, frame, dict(state, previous_strategy=self.strategy,
                                                  previous_action=self.previous_action[team], role='strategy'))
        interval = (self.config.get('reaction_interval_seconds', 1) if self.urgent[team]
                    else self.config.get('tactical_interval_seconds', 3))
        if (team not in self.busy and self.calls[team] < self.config['max_calls_per_team']
                and now-self.last[team] >= interval):
            self.busy.add(team)
            self.calls[team] += 1
            self.last[team] = now
            self.urgent[team] = False
            strategy = self.strategy if frame-self.strategy_frame <= 1800 else None
            context = dict(state, previous_action=self.previous_action[team],
                           candidate_actions=candidates_for(state), rules=SYSTEM)
            if team == 0:
                context['strategy'] = strategy
            self.pool.submit(self.tactics, team, frame, context, self.epoch[team])

    def plan(self, frame, state):
        try:
            if self.mock:
                action, metrics = candidates_for(state)['attack_base'], {'latency_seconds': 0, 'mock': True}
            else:
                action, metrics = chat(self.config, self.models[0], state)
            with self.lock:
                stale = self.finished or self.latest_frame-frame > 1800
                self.log('strategy', team=0, frame=frame, model=self.models[0], action=action, stale=stale, **metrics)
                if not stale:
                    self.strategy, self.strategy_frame = action, frame
        except Exception as exc:
            with self.lock:
                self.log('strategy_error', team=0, frame=frame, error_type=type(exc).__name__, status=getattr(exc, 'code', None))
        finally:
            with self.lock:
                self.strategy_busy = False

    def local_tactics(self, context, choices):
        return jev.choose(self.config, context, choices)

    def record_tactics(self, team, frame, action, metrics, context):
        pass

    def tactics(self, team, frame, context, epoch):
        model = (self.models[0] if self.config.get('local_council_enabled') else self.config.get('jev_model', 'jev-latest')) if team == 0 else self.models[1]
        try:
            choices = context['candidate_actions']
            if self.mock:
                action, metrics = choices['attack_base'], {'latency_seconds': 0, 'mock': True}
            elif team == 0:
                action, metrics = self.local_tactics(context, choices)
            else:
                action, metrics = council.consult(dict(self.config, request_timeout_seconds=
                    self.config.get('tactical_timeout_seconds', 5)), model, 'solo', context, choices, {})
            validate_action(action)
            if action not in choices.values():
                raise ValueError('Action outside candidates')
            with self.lock:
                stale = (self.finished or self.latest_frame-frame > self.config.get('command_max_age_frames', 150)
                         or epoch != self.epoch[team])
                latest = candidates_for(self.states[team])
                # Moving targets may change; production prerequisites must still hold.
                valid = (action['action'] not in ('produce', 'economy') or action in latest.values())
                self.log('decision', team=team, frame=frame, model=model, action=action,
                         stale=stale, executable=valid, **metrics)
                if not stale and valid:
                    self.record_tactics(team, frame, action, metrics, context)
                    self.previous_action[team] = action
                    self.pending.append(dict(team=team, frame=frame, **action))
        except Exception as exc:
            with self.lock:
                self.log('error', team=team, frame=frame, model=model,
                         error_type=type(exc).__name__, status=getattr(exc, 'code', None))
        finally:
            with self.lock:
                self.busy.discard(team)


class CouncilMatch(HybridMatch):
    """Two advisory specialists and one final-action specialist share a scratchpad."""
    def __init__(self, config, token, log_dir, mock=False):
        super().__init__(config, token, log_dir, mock)
        self.scratchpad = council.Scratchpad(log_dir, mock, persist=config.get('persist_memory', True))

    def plan(self, frame, state):
        try:
            for role in ('strategy', 'economy'):
                with self.lock:
                    if self.finished:
                        return
                    memory = self.scratchpad.context()
                    # Each role starts from the freshest available observation.
                    current = dict(self.states.get(0, state), rules=SYSTEM)
                    observed_frame = current.get('frame', frame)
                try:
                    if self.mock:
                        action, metrics = candidates_for(current)['attack_base'], dict(
                            latency_seconds=0, mock=True, role=role, note='Mock specialist recommendation.')
                    else:
                        action, metrics = council.consult(self.config, self.models[0], role,
                            current, candidates_for(current), memory)
                    with self.lock:
                        stale = self.finished or self.latest_frame-observed_frame > 1800
                        self.log('strategy', team=0, frame=observed_frame, model=self.models[0],
                                 action=action, stale=stale, **metrics)
                        if not stale:
                            self.scratchpad.append(role, observed_frame, action, metrics['note'], current)
                            if role == 'strategy':
                                self.strategy, self.strategy_frame = action, observed_frame
                except Exception as exc:
                    with self.lock:
                        self.log('strategy_error', team=0, frame=observed_frame, role=role,
                                 error_type=type(exc).__name__, status=getattr(exc, 'code', None))
        finally:
            with self.lock:
                self.strategy_busy = False

    def local_tactics(self, context, choices):
        with self.lock:
            memory = self.scratchpad.context()
        # The cloud side uses the same tactical timeout and action candidates.
        config = dict(self.config, request_timeout_seconds=self.config.get('tactical_timeout_seconds', 10))
        return council.consult(config, self.models[0], 'tactical', context, choices, memory)

    def record_tactics(self, team, frame, action, metrics, context):
        if team == 0:
            self.scratchpad.append('tactical', frame, action,
                metrics.get('note', 'Mock tactical decision.'), context)

    def handle(self, message):
        reply = super().handle(message)
        if isinstance(message, dict) and message.get('kind') == 'finished' and reply.get('finished'):
            with self.lock:
                self.scratchpad.finish(message['winner'], message['frame'],
                    dict(models=self.models, map=self.states.get(0, {}).get('map', 'unknown'),
                         controller='local-council-v1'))
        return reply


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        while True:
            try:
                line = self.rfile.readline(131073)
                if not line or len(line) > 131072:
                    return
                response = self.server.match.handle(json.loads(line))
                self.wfile.write((json.dumps(response) + "\n").encode())
                self.wfile.flush()
            except (ValueError, OSError, TypeError):
                return


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = not hasattr(socket, "SO_EXCLUSIVEADDRUSE")
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--session", type=Path)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--probe-timeout", type=float, default=180,
                        help="Readiness timeout including cold model loading; match timeout is unchanged")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    if args.probe:
        if not 0 < args.probe_timeout <= 3600:
            parser.error("--probe-timeout must be between 0 and 3600 seconds")
        config = dict(config, request_timeout_seconds=args.probe_timeout)
        state = {"team": 0, "metal": 1500, "energy": 10000, "combat_units": 6,
                 "enemy_base": {"x": 0.8, "z": 0.8}, "enemies": []}
        failed = False
        if config.get("hybrid_enabled"):
            try:
                jev.require_key()
                action, metrics = jev.choose(config, state, candidates_for(state))
                print(json.dumps({"model": config.get("jev_model"), "action": action, **metrics}), flush=True)
            except Exception as exc:
                print(json.dumps({"model": "JEV", "error_type": type(exc).__name__,
                                  "setup_required": not bool(os.environ.get('TYPESAFE_API_KEY'))}), flush=True)
                raise SystemExit(1)
        for model in (config["local_model"], config["cloud_model"]):
            try:
                action, metrics = chat(config, model, state)
                print(json.dumps({"model": model, "action": action, **metrics}), flush=True)
            except Exception as exc:
                print(json.dumps({"model": model, "error_type": type(exc).__name__,
                                  "status": getattr(exc, "code", None)}), flush=True)
                failed = True
        raise SystemExit(1 if failed else 0)
    session = json.loads(args.session.read_text(encoding="utf-8-sig"))
    if session.get("test_run"):
        config = dict(config, persist_memory=False)
    match_type = CouncilMatch if config.get("local_council_enabled") else (HybridMatch if config.get("hybrid_enabled") else Match)
    if config.get("hybrid_enabled") and not args.mock:
        jev.require_key()
    match = match_type(config, session["token"], args.session.parent, args.mock)
    with Server(("127.0.0.1", config["port"]), Handler) as server:
        server.match = match
        (args.session.parent / "bridge.ready").write_text("ready", encoding="ascii")
        print("BAR duel bridge ready on loopback port", config["port"], flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
