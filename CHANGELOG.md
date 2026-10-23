# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `make install` and `make uninstall`: installs from source with the dependencies on Debian,
  Fedora, openSUSE and Arch based distributions; uninstalling removes only the dependencies
  it installed and nothing else needs.

## [0.1.0] - 2026-10-23

### Added

- <kbd>Pause</kbd> retypes the end of the text typed in the wrong layout, using hunspell
  dictionaries to find where it starts; pressing it again cycles the same text through the
  layouts.
- <kbd>Shift</kbd>+<kbd>Pause</kbd> retypes the selected text.
- <kbd>Ctrl</kbd>+<kbd>Pause</kbd> cycles the case of the selected text: lower, UPPER, Title.
- Any number of layouts; with three or more, the dictionaries pick the target layout.
- Tray indicator: flag, layout name, both, the app icon or none, with light and dark themes.
- Global shortcuts registered with KDE and set in System Settings (Pause, Shift+Pause,
  Ctrl+Pause by default).
- Settings: sound, autostart, custom flag pictures, diagnostics with dictionary
  install hints and download.
- Interface in English and Russian (gettext); more languages can be added in `po/`.
- Debian package.

[Unreleased]: https://github.com/DayDve/ntrcn/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/DayDve/ntrcn/releases/tag/v0.1.0
