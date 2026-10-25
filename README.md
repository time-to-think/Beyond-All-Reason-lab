# Beyond-All-Reason lab

Personal BAR AI experiments comparing local Qwen3.5 4B and Ollama Cloud GPT-OSS 120B in the same bounded strategy scenario. This is an experimental wrapper, not a complete autonomous BAR player.

| Path | Purpose |
| --- | --- |
| `Beyond-All-Reason/` | Pinned team game source and assets (Git submodule) |
| `agent/` | Model bridge, prompts, configuration |
| `game-extension/` | Personal duel mode, loaded as a dependent game archive |
| `launcher/` | Python launcher and log auditor |
| `tests/` | Python and Lua 5.1 contract tests |
| `docs/` | Usage, workflow, validation, AI research |

## Setup

```sh
git clone --filter=blob:none --recurse-submodules https://github.com/time-to-think/Beyond-All-Reason-lab.git
cd Beyond-All-Reason-lab
python launcher/start_duel.py --data-dir /path/to/BAR/data --engine-dir /path/to/recoil
```

Use Python 3.12+. Install a compatible native Recoil build, base files, fonts, Comet Catcher Remake map, and Ollama separately. The submodule contains game content, not the Recoil executable. On Windows, `Start-LLM-Duel.cmd` and the existing desktop shortcut remain valid. Machine-local paths may be saved in ignored `launcher/local.json`.

The launcher uses Python with Windows junctions and POSIX symbolic links. Native macOS/Linux game execution still requires validation on those platforms.

- [Usage](docs/USAGE.md)
- [Repository workflow](docs/REPOSITORY_WORKFLOW.md)
- [Validation](docs/VALIDATION.md)
- [AI candidates and evaluation plan](docs/AI_RESEARCH.md)

## Development

```sh
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -p 'test_*.py'
git -C Beyond-All-Reason status --short
```

Keep personal AI and launcher changes in this lab. Necessary shared game changes go through a personal game fork and team PR. Use English for documents, comments, and new commit messages. Historical development commits remain available in the personal game fork and its archive branch; the lab starts with a clean source snapshot.

Licenses in `LICENSE.md`, the submodule, and individual files apply. Codex assisted implementation and testing. Shared contributions require human review under the team's contribution policy.
