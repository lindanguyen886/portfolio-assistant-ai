import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

DATA_DIR = os.path.join(BASE_DIR, "data")

HOLDINGS_FILE = os.path.join(DATA_DIR, "holdings.json")
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")


def load_env_file(path=ENV_FILE):
    """
    Lightweight .env loader for KEY=VALUE lines.
    Existing environment variables are not overridden.
    """
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


def get_openai_api_key():
    """
    Resolve OPENAI_API_KEY from environment, then local .env fallback.
    """
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    load_env_file()
    return os.environ.get("OPENAI_API_KEY")


def assert_openai_api_key():
    key = get_openai_api_key()
    if not key:
        raise RuntimeError(
            "Missing OPENAI_API_KEY. Set it in your environment or in "
            f"{ENV_FILE} (example: OPENAI_API_KEY=your_key_here)."
        )

    normalized = key.strip()
    placeholder_tokens = [
        "your_openai_api_key_here",
        "your_ope",
        "placeholder",
        "replace_me",
    ]
    if (
        len(normalized) < 20
        or any(token in normalized.lower() for token in placeholder_tokens)
        or not normalized.startswith("sk-")
    ):
        raise RuntimeError(
            "OPENAI_API_KEY appears invalid or still a placeholder. "
            f"Update {ENV_FILE} with a real key from platform.openai.com."
        )
    return key
