# Repository workflow

| Role | Repository |
| --- | --- |
| canonical game | `beyond-all-reason/Beyond-All-Reason` |
| upstream team game | `time-to-think/Beyond-All-Reason` |
| origin personal game fork | `mangman4/Beyond-All-Reason` |
| upstream team experiment lab | `time-to-think/Beyond-All-Reason-lab` |
| origin personal experiment lab fork | `mangman4/Beyond-All-Reason-lab` |

The lab's `origin` points to the personal lab fork and `upstream` points to the team lab. The default push remote is `origin`. The canonical/upstream/origin game workflow applies in a separate game checkout; the lab has no separate canonical game remote. Do not send lab changes to the team game repository.

The `Beyond-All-Reason/` submodule consumes a pinned team game commit. Keep it detached and clean during experiments. Personal Lua loads through a dependent game archive and is never copied into the game source.

## Personal changes

Create a `codex/` branch, modify the lab, test, inspect staged paths, and push to the lab's origin. Exclude credentials, session files, weights, binaries, meeting notes, and unrelated work. Documents, comments, and commit messages must be English.

Open a PR from `mangman4/Beyond-All-Reason-lab:<branch>` to `time-to-think/Beyond-All-Reason-lab:master` for team review. Do not push directly to the team default branch. Fetch `upstream` to obtain reviewed lab changes. The team lab was established by transferring the existing standalone lab and forking it back to the personal account, preserving the existing commits and development branch.

## Shared game changes

```sh
git clone https://github.com/mangman4/Beyond-All-Reason.git bar-core-work
cd bar-core-work
git remote add upstream https://github.com/time-to-think/Beyond-All-Reason.git
git remote add canonical https://github.com/beyond-all-reason/Beyond-All-Reason.git
git fetch upstream
git switch -c codex/shared-fix upstream/master
# Make only the necessary shared game change and validate it.
git push -u origin codex/shared-fix
```

Open a PR from the personal branch to the team repository for human review. Never directly push the team default branch. Team maintainers synchronize canonical updates through review; experiments do not silently update the game version.

## Update the pinned game

```sh
git -C Beyond-All-Reason fetch origin master
git -C Beyond-All-Reason switch --detach origin/master
git -C Beyond-All-Reason submodule update --init --recursive
python -m unittest discover -s tests -p 'test_*.py'
git add Beyond-All-Reason
git commit -m "Update pinned team BAR revision"
git push origin HEAD
```

Other clones use `git pull` and `git submodule update --init --recursive`.

## Migration

Previous development history is preserved in the personal game fork and its `codex/pre-lab-migration` archive branch. The new lab starts from a clean source snapshot so it does not duplicate the game asset history. The personal game fork is restored with a forward commit, not a force push. The outer local directory and `Start-LLM-Duel.cmd` path stay unchanged for desktop compatibility. The old submodule path `engine/` is replaced with the original game name.
