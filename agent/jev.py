"""TypeSafe Choice adapter. Credentials stay in the process environment."""
import json
import os
import time
import urllib.request


def require_key():
    key = os.environ.get('TYPESAFE_API_KEY', '').strip()
    if not key:
        raise ValueError('JEV requires TYPESAFE_API_KEY; use launcher/setup_jev.py')
    return key


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def choose(config, state, candidates):
    body = {'model': config.get('jev_model', 'jev-latest'), 'state': state,
            'questions': {'action': {'type': 'choice',
                'instructions': 'Choose the next BAR action. Protect the commander, respond to visible threats, '
                                'and pursue the strategy when safe. Only visible enemies are known.',
                'criteria': {key: json.dumps(value) for key, value in candidates.items()}}}}
    request = urllib.request.Request('https://api.typesafe.ai/v1/systemone',
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json',
                                               'Authorization': 'Bearer ' + require_key()})
    start = time.monotonic()
    with urllib.request.build_opener(NoRedirect).open(
            request, timeout=config.get('tactical_timeout_seconds', 5)) as response:
        result = json.load(response)
    answer = result['answers']['action']
    key = answer.get('choice')
    if answer.get('type') != 'choice' or not isinstance(key, str) or key not in candidates:
        raise ValueError('Invalid JEV choice')
    return candidates[key], {'latency_seconds': round(time.monotonic() - start, 3),
                             'reported_model': result.get('model'), 'choice': key,
                             'usage': result.get('usage'), 'confidence': answer.get('confidence')}
