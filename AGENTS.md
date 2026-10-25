# Personal BAR LLM project

- This repository belongs to `mangman4/Beyond-All-Reason-lab`. Personal agent, game-extension, launcher, test and documentation changes belong here.
- The personal lab is a fork of `time-to-think/Beyond-All-Reason-lab`. Use `origin` for the personal lab and `upstream` for the team lab; propose lab changes through a PR for team review.
- `Beyond-All-Reason/` is the shared `time-to-think/Beyond-All-Reason` submodule, pinned to a specific commit. It contains BAR game content; the Recoil executable is installed separately.
- Do not put personal features in `Beyond-All-Reason/` or push them to the team game repository. Shared core changes require a separate branch and team review. Do not push to either team repository's default branch as part of personal work.
- Load personal Lua through the dependent game archive in `game-extension/`. Do not copy personal files into the submodule.
- Before uploading, verify the Git remote, submodule status, tests and staged paths. Exclude account credentials, local session data, meeting notes and run logs.
- Tests: install `requirements-test.txt`, then `python -m unittest discover -s tests -p "test_*.py"`. Lua tests use the game submodule's JSON implementation and the personal extension's Lua files.
- Preserve `Start-LLM-Duel.cmd` at the root so existing desktop shortcuts continue to work.

- Write documents, code comments, and commit messages in English.
- Keep launcher behavior in portable Python; PowerShell is a legacy forwarding shim only.
- Keep the personal game fork separate from this lab; use origin/upstream/canonical in the game checkout.
