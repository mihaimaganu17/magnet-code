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
AGENT_MD_FILE = "agent.md"

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

def _get_project_config(cwd: Path) -> Path | None:
    current = cwd.resolve()
    agent_dir = current / '.magnet'
    
    if agent_dir.is_dir():
        config_file = agent_dir / CONFIG_FILE_NAME
        if config_file.is_file():
            return config_file
        
    return None

def _get_agent_md_files(cwd: Path) -> Path | None:
    """Reads any `AGENTS.md` file present in the current working directory"""
    current = cwd.resolve()
    
    if current.is_dir():
        agent_md_file = current / AGENT_MD_FILE
        if agent_md_file.is_file():
            content = agent_md_file.read_text(encoding='utf-8')
            return content
        
    return None

def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge the 2 given dictionaries. We start with the `base` dictionary and if we find any
    overlapping items in the `override` one, we override it"""
    # The base is our starting point
    result = base.copy()
    
    # For each key in the override dict
    for key, value in override.items():
        # If the key is present in result and it's value is another dictionary
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively resolve it as a merge as well
            result[key] = _merge_dicts(result[key], value)
        else:
            # Otherwise, simple assignment
            result[key] = value
    return result

def load_config(cwd: Path | None) -> Config:
    """Load a magnet configuration file from the specified path or one of the default paths (system)
    of local relative `.magnet/config.toml` paths"""
    cwd = cwd or Path.cwd()
    
    system_path = get_system_config_path()
    
    config_dict: dict[str, Any] = {}
    
    # Reading the system-wide config file (~/.config/magnet/config.toml)
    if system_path.is_file():
        try:
            config_dict = _parse_toml(system_path)
        except ConfigError:
            logger.warning(f"Skipping invalid system config: {system_path}")
    
    # Reading the configuration file in the local directory (.magnet/config.toml)
    project_path = _get_project_config(cwd)
    if project_path:
        try:
            project_config_dict = _parse_toml(project_path)
            # The local relative config file takes precedence (overrides) the system one and we send
            # the two to be merged together with that in mind
            config_dict = _merge_dicts(config_dict, project_config_dict)
        except ConfigError:
            logger.warning(f"Skipping invalid system config: {system_path}")

    # If the configuration file does not have a working directory for the agent's execution, we
    # make the directory of the configuration file or the curren execution directory of the
    # `magnet-code` binary
    if "cwd" not in config_dict:
        config_dict["cwd"] = cwd

    if "developer_instructions" not in config_dict:
        agent_md_content = _get_agent_md_files(cwd)
        if agent_md_content:
            config_dict["developer_instructions"] = agent_md_content
            
    try:
        # Instatiate our config with the desired options
        config = Config(**config_dict)
    except Exception as e:
        raise ConfigError(f"Invalid configuration: {e}") from e
    
    return config