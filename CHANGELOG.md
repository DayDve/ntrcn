# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- <kbd>Pause</kbd> retypes the end of the text typed in the wrong layout, using hunspell
  dictionaries to find where it starts; pressing it again cycles the same text through the
  layouts.
- <kbd>Shift</kbd>+<kbd>Pause</kbd> retypes the selected text.
- Any number of layouts; with three or more, the dictionaries pick the target layout.
- Tray indicator: flag, layout name, both, the app icon or none, with light and dark themes.
- Settings: hotkey, sound, autostart, custom flag pictures, diagnostics with dictionary
  install hints and download.
- Debian package.
