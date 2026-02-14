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

            if isinstance(args, {}):
                for k in sorted(args.keys()):
                    output.append(f"{k}={str(args[k])}")

        elif action_type == 'response':
            output.append(details.get('text', ''))

        signature = "|".join(output)
        self._history.append(signature)