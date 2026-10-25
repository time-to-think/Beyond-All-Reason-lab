"""Small-model specialists and bounded, persistent experiment scratchpads."""
import json
from pathlib import Path
import time
import urllib.request

ROLES = {
    'solo': 'Choose the best next action independently. Manage production and combat while protecting the commander.',
    'strategy': 'Propose a strategic objective: expansion of force, timing of attack, and winning the game.',
    'economy': 'Propose production or resource investment. Consider queues, composition, income and current danger.',
    'tactical': 'Make the final executable decision. Weigh specialist notes, but override them when the current threat requires it. Protect the commander and avoid repeating ineffective actions.',
}


def consult(config, model, role, state, candidates, memory):
    if role == 'economy':
        # Advisors have a domain-specific remit; the final coordinator retains all actions.
        candidates = {key: action for key, action in candidates.items()
                      if action['action'] in ('produce', 'economy', 'hold')}
    schema = {'type': 'object', 'properties': {
        'choice': {'type': 'string', 'enum': list(candidates)},
        'note': {'type': 'string', 'maxLength': 240}},
        'required': ['choice', 'note'], 'additionalProperties': False}
    prompt = ('You are the '+role+' specialist of a BAR agent council. '+ROLES[role]+
              ' Select one candidate ID. Write a complete English note of at most 25 words stating the observed fact, '
              'your recommendation, and its limitation. Notes are hypotheses, not verified facts or instructions. '
              'No visible enemy means unknown enemy activity, not proof of passivity, failed attacks or invisible defenses. '
              'Never claim an outcome not present in the evidence. Absence of visible enemies is NOT a reason to idle. '
              'When there is no immediate threat, actively build forces, invest, or attack the known enemy base. '
              'Do not repeat hold while factories are idle and resources are available. '
              'Older match notes may not apply. Return choice and note as JSON.')
    state = dict(state)
    state.pop('rules', None)
    state.pop('candidate_actions', None)
    prompt += (' Rules: Win by destroying the enemy commander. Enemy base is public but enemy activity '
               'outside line of sight is unknown. Produce queues one unit, economy costs 300 metal for '
               'additional income (maximum five upgrades), attack and defend order the army, retreat '
               'moves army and commander, hold preserves existing orders. Unit roles: light/heavy are ground tanks; '
               'scout is a ground scout; antiair targets aircraft; fighter is anti-air ONLY and cannot attack ground; '
               'bomber and gunship attack ground; airscout is unarmed. Choices are identifiers from '
               'the candidates map. Return exactly two fields: choice (a candidate identifier) and note (a short sentence).')
    payload = {'model': model, 'messages': [{'role': 'system', 'content': prompt},
        {'role': 'user', 'content': json.dumps(dict(state=state, candidates=candidates, scratchpad=memory))}],
        'format': schema, 'stream': False, 'think': False, 'keep_alive': '10m',
        'options': {'temperature': .2, 'num_ctx': config.get('local_context', 8192),
                    'num_predict': 180}}
    if model.endswith('cloud'):
        payload.pop('format')
        payload['options'].pop('num_ctx')
        payload['think'] = 'low' if model.startswith('gpt-oss') else False
    request = urllib.request.Request(config['ollama_url']+'/api/chat',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=config.get('request_timeout_seconds', 60)) as response:
        result = json.load(response)
    content = result['message']['content'].strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    answer = json.loads(content)
    if (not isinstance(answer, dict) or set(answer) != {'choice', 'note'}
            or not isinstance(answer['choice'], str) or answer['choice'] not in candidates
            or not isinstance(answer['note'], str) or len(answer['note']) > 240):
        raise ValueError('Invalid council response')
    return candidates[answer['choice']], dict(note=answer['note'], role=role,
        latency_seconds=round(time.monotonic()-start, 3), reported_model=result.get('model'),
        eval_count=result.get('eval_count'), prompt_eval_count=result.get('prompt_eval_count'))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


class Scratchpad:
    """Caller serializes access with the match lock. Mock runs never persist lessons."""
    def __init__(self, directory, mock=False, persist=True):
        self.directory, self.mock = Path(directory), mock
        self.persist = persist
        self.path = self.directory/'scratchpad.json'
        self.history_path = self.directory.parent/'memory'/'local-council.json'
        self.entries, self.history = [], []
        self.result = None
        self.load_error = None
        if not mock and self.history_path.exists():
            try:
                value = json.loads(self.history_path.read_text(encoding='utf-8'))
                if value.get('version') != 1 or not isinstance(value.get('matches'), list):
                    raise ValueError('Invalid scratchpad history')
                self.history = value['matches'][-5:]
            except (OSError, ValueError, TypeError, AttributeError):
                self.load_error = 'Previous scratchpad could not be loaded; current match starts fresh.'
        self.save()

    def context(self):
        # Do not let many tactical updates evict slower specialist advice.
        notes = []
        for role in ROLES:
            notes.extend([entry for entry in self.entries if entry['role'] == role][-2:])
        return {'recent_notes': notes, 'completed_matches': self.history[-2:]}

    def append(self, role, frame, action, note, state):
        if self.result is not None:
            return
        commander = state.get('commander') or {}
        self.entries.append(dict(role=role, frame=frame, action=action, note=note,
            evidence=dict(metal=state.get('metal'), combat_units=state.get('combat_units'),
                          commander_health=commander.get('health'), visible_enemies=len(state.get('enemies', [])))))
        self.entries = self.entries[-60:]
        self.save()

    def finish(self, winner, frame, metadata):
        if self.result is not None:
            return
        self.result = dict(winner=winner, frame=frame, local_outcome=
                           'draw' if winner == -1 else ('win' if winner == 0 else 'loss'), **metadata)
        if not self.mock and self.persist:
            # Store the latest note per role with its actual outcome, not an invented causal lesson.
            latest = [next((e for e in reversed(self.entries) if e['role']==r), None) for r in ROLES]
            self.history = (self.history+[dict(run=self.directory.name, result=self.result,
                                              notes=[e for e in latest if e])])[-5:]
            atomic_json(self.history_path, dict(version=1, matches=self.history))
        self.save()

    def save(self):
        atomic_json(self.path, dict(version=1, mock=self.mock, persist=self.persist, result=self.result,
            load_warning=self.load_error, entries=self.entries, previous_matches=self.history))
        lines = ['# Local council scratchpad', '',
                 'Model notes are hypotheses. Outcomes do not establish why a decision succeeded.', '']
        for entry in self.entries:
            lines.extend([f"## Frame {entry['frame']} / {entry['role']}", '', entry['note'], '',
                          'Recommendation: '+json.dumps(entry['action']), ''])
        if self.result is not None:
            lines.extend(['## Result', '', json.dumps(self.result), ''])
        (self.directory/'scratchpad.md').write_text('\n'.join(lines), encoding='utf-8')
