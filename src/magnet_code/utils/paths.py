from pathlib import Path

def resolve_path(base: str | Path, path: str | Path):
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    
    # Susceptible to evasion with ../..
    return Path(base).resolve() / path

def is_binary_file(path: str | Path) -> bool:
    """Basic heuristic to check for binary file"""
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
            return 0x00 in chunk
    except (OSError, IOError):
        return False