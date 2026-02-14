from collections import deque
from typing import Any


class LoopDetector:
    def __init__(self):
        # Catch the number of times an agent action repeats
        self.max_exact_repeats = 3
        self.max_cycle_length = 3 # A->B->A->B
        # Keep the latest actions
        self._history: deque[str] = deque(maxlen=20)

    def record_action(self, action_type: str, **details: Any):
        """Records an agent action"""
        # TODO: Need to hash the action that we are storing for faster comparison
        output = [action_type]

        if action_type == 'tool_call':
            output.append(details.get('tool_name', ''))
            args = details.get('args', {})

            if isinstance(args, dict):
                for k in sorted(args.keys()):
                    output.append(f"{k}={str(args[k])}")

        elif action_type == 'response':
            output.append(details.get('text', ''))

        signature = "|".join(output)
        self._history.append(signature)

    def check_for_loop(self) -> str | None:
        if len(self._history) < 2:
            return None

        # First we check if a single element is repeating
        if len(self._history) >= self.max_exact_repeats:
            recent = list(self._history)[-self.max_exact_repeats:]

            if len(set(recent)) == 1:
                return f"Same action repeated {self.max_exact_repeats} times"

        # Check if there is a cycle
        if len(self._history) >= self.max_cycle_length * 2:
            for cycle_len in range(2, self.max_cycle_length + 1):
                recent = self._history[-cycle_len * 2:]
                if recent[:cycle_len] == recent[cycle_len:]:
                    return f"Detected repeating cycle of length {cycle_len}"

        return None