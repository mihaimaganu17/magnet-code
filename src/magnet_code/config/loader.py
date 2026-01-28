from pathlib import Path
import tomllib
from typing import Any
from platformdirs import user_config_dir
from magnet_code.config.config import Config
from magnet_code.utils.errors import ConfigError
import logging
from tomllib import TOMLDecodeError

logger = logging.getLogger(__name__)

CONFIG_FILE_NAME = "config.toml"

def get_config_dir() -> Path:
    return Path(user_config_dir('magnet'))

def get_system_config_path() -> Path:
    return get_config_dir() / CONFIG_FILE_NAME

def _parse_toml(path: Path) -> dict[str, Any] | None:
    try:
        content = None
        with open(path, 'rb') as f:
           content = tomllib.load(f)
        return content
    except tomllib.TOMLDecodeError as e:
        raise ConfigError("Invalid TOML in {path}: {e}", config_file=str(path)) from e
    except (OSError, IOError) as e:
        raise ConfigError("Failed to read config file {path}: {e}", config_file=str(path)) from e

def load_config(cwd: Path | None) -> Config:
    cwd = cwd or Path.cwd()
    
    system_path = get_system_config_path()
    
    config_dict: dict[str, Any] = {}
    
    if system_path.is_file():
        try:
            config_dict = _parse_toml(system_path)
        except ConfigError:
            logger.warning(f"Skipping invalid system config: {system_path}")