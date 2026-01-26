from pathlib import Path

def resolve_path(base: str | Path, path: str | Path):
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    
    # Susceptible to evasion with ../..
    return Path(base).resolve() / path