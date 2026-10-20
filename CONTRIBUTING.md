# Contributing

## Setup

```bash
python3 -m venv --system-site-packages .venv && .venv/bin/pip install pytest ruff mypy
make check   # ruff, mypy --strict, pytest: must pass before every commit
```

Changes to input handling, layouts or typing must also be checked on a live Plasma session
with `make e2e`.

## Code

- Python 3.10+, type hints everywhere, `mypy --strict` for `src/`, `ruff` with 100 columns.
- Keep it simple: no layers or options "for later". Pure logic (`keys.py`, `convert.py`) stays
  free of I/O and is covered by unit tests; system glue stays thin.
- Docstrings for public modules, classes and functions; `logging` instead of `print`.
- Never log typed text or key codes.
- The udev rule only matches the `uinput` node. Input devices are read without grabbing them.

## Translations

The interface is written in English and translated with gettext (domain `ntrcn`).

- Wrap user-visible strings in `_()` from `ntrcn.i18n`; strings defined at import time are
  marked with `N_()` and translated with `_()` where they are shown.
- `make pot` extracts the strings into `po/ntrcn.pot` and updates every `po/<lang>.po`.
- To add a language, copy `po/ntrcn.pot` to `po/<lang>.po` and translate it.
- `make translations` compiles the catalogs for running from the source tree; packages compile
  them at build time.

## Git

- `master` holds releases tagged `vX.Y.Z`, `develop` is the integration branch, work happens on
  `feature/<name>` branches from `develop`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(converter): ...`, `fix(tray): ...`.
- Versions follow [SemVer](https://semver.org/); user-visible changes go to the
  `[Unreleased]` section of `CHANGELOG.md`.

## Release

1. Branch `release/vX.Y.Z` from `develop`; set the version in `pyproject.toml`,
   `src/ntrcn/__init__.py` and `debian/changelog`; move `[Unreleased]` in `CHANGELOG.md` to
   `[X.Y.Z] - YYYY-MM-DD`.
2. `make check deb deb-check deb-test`.
3. Merge into `master`, tag `vX.Y.Z`, merge back into `develop`, attach the `.deb` to the
   GitHub release.
