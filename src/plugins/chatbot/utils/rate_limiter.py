import time

_usage: dict[str, float] = {}
_COOLDOWN = 60


def check(user_id: str) -> bool:
    now = time.time()
    expired = [k for k, v in _usage.items() if now - v > _COOLDOWN * 2]
    for k in expired:
        del _usage[k]
    if now - _usage.get(user_id, 0) < _COOLDOWN:
        return False
    _usage[user_id] = now
    return True


def remaining(user_id: str) -> int:
    last = _usage.get(user_id, 0)
    return max(0, int(_COOLDOWN - (time.time() - last)))
