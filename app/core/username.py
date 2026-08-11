def normalize_username(username: str) -> str:
    return username.strip()


def is_valid_username(username: str) -> bool:
    if not username or len(username) > 64:
        return False
    return not any(ord(c) < 32 or ord(c) == 127 for c in username)
