from pathlib import Path
from tomllib import TOMLDecodeError
from platformdirs import user_config_dir
from magnet_code.config.config import Config

CONFIG_FILE_NAME = "config.toml"

def get_config_dir() -> Path:
    return Path(user_config_dir('magnet'))

def get_system_config_path() -> Path:
    return get_config_dir() / CONFIG_FILE_NAME

def _parse_toml(path: Path):
    try:
        pass
    except TOMLDecodeError as e:
        raise ConfigError()

def load_config(cwd: Path | None) -> Config:
    cwd = cwd or Path.cwd()
    
    system_path = get_system_config_path()
    
    if system_path.is_file():