"""Prompt privately for a session-only JEV key, then launch the duel."""
import getpass
import os
from pathlib import Path
import subprocess
import sys


def main():
    print('Create a TypeSafe API key at https://typesafe.ai first.')
    print('The key is hidden and used only for this launch. It is not saved to disk.')
    key = getpass.getpass('TypeSafe API key: ').strip()
    if not key:
        print('No key entered; cancelled.')
        return 1
    environment = dict(os.environ, TYPESAFE_API_KEY=key)
    return subprocess.call([sys.executable, str(Path(__file__).with_name('start_duel.py')),
                            *sys.argv[1:]], env=environment)


if __name__ == '__main__':
    raise SystemExit(main())
