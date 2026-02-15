from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import json
import os
from typing import Any
from magnet_code.config.loader import get_data_dir


@dataclass
class SessionSnahpshot:
    session_id: str
    created_at: datetime
    updated_at: datetime
    turn_count: int
    messages: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "turn_count": self.turn_count,
            "messages": self.messages,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionSnahpshot:
        return cls(
            session_id=data["session_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            turn_count=data["turn_count"],
            messages=data["messages"],
        )



class PersistenceManager:
    def __init__(self):
        self.data_dir = get_data_dir()
        self.sessions_dir = self.data_dir / 'sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.sessions_dir, 0o700)

    def save_session(self, snapshot: SessionSnahpshot) -> None:
        file_path = self.sessions_dir / f"{snapshot.session_id}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

        # ReadWrite permissions
        os.chmod(file_path, 0o600)