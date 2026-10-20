from pathlib import Path

from ntrcn.config import Config, load_config, save_config


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    assert load_config(tmp_path / "none.json") == Config()


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    config = Config(
        sound="custom",
        sound_file="/x.oga",
        tray_indicator="none",
        app_icon_theme="color",
    )
    save_config(config, path)
    assert load_config(path) == config


def test_invalid_values_fall_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"sound": "loud", "tray_indicator": "huge", "text_theme": "color"}')
    assert load_config(path) == Config()


def test_broken_json_gives_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not json")
    assert load_config(path) == Config()
