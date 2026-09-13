import json
import os
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SETTINGS_PATH = DATA_DIR / "settings.json"
API_KEY_PATH = DATA_DIR / "mirror-api-key"

DEFAULT_CATALOG_URL = os.environ.get(
    "TAPEBOX_CATALOG_URL",
    "http://tapebox:8080/api/catalog-mirror/download",
)


def _defaults():
    parsed = urlparse(
        DEFAULT_CATALOG_URL
    )

    return {
        "scheme": (
            parsed.scheme
            if parsed.scheme in ("http", "https")
            else "http"
        ),
        "host": parsed.hostname or "tapebox",
        "port": parsed.port or 8080,
    }


def get_settings():
    defaults = _defaults()

    if not SETTINGS_PATH.is_file():
        return defaults

    try:
        saved = json.loads(
            SETTINGS_PATH.read_text()
        )

    except Exception:
        return defaults

    return {
        "scheme": saved.get(
            "scheme",
            defaults["scheme"],
        ),
        "host": saved.get(
            "host",
            defaults["host"],
        ),
        "port": saved.get(
            "port",
            defaults["port"],
        ),
    }


def save_settings(
    scheme,
    host,
    port,
):
    scheme = (
        scheme or ""
    ).strip().lower()

    host = (
        host or ""
    ).strip()

    if scheme not in (
        "http",
        "https",
    ):
        raise ValueError(
            "Protocol must be HTTP or HTTPS."
        )

    if not host:
        raise ValueError(
            "TapeBox server address is required."
        )

    if (
        "/" in host
        or "\\" in host
        or "://" in host
    ):
        raise ValueError(
            "Enter only the server IP address or hostname."
        )

    try:
        port = int(port)

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Port must be a number."
        )

    if not 1 <= port <= 65535:
        raise ValueError(
            "Port must be between 1 and 65535."
        )

    settings = {
        "scheme": scheme,
        "host": host,
        "port": port,
    }

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = SETTINGS_PATH.with_suffix(
        ".json.tmp"
    )

    temp_path.write_text(
        json.dumps(
            settings,
            indent=2,
        )
    )

    os.replace(
        temp_path,
        SETTINGS_PATH,
    )

    return settings


def save_api_key(api_key):
    api_key = (
        api_key or ""
    ).strip()

    if not api_key:
        return False

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = API_KEY_PATH.with_suffix(
        ".tmp"
    )

    temp_path.write_text(
        api_key + "\n"
    )

    temp_path.chmod(
        0o600
    )

    os.replace(
        temp_path,
        API_KEY_PATH,
    )

    return True


def api_key_configured():
    try:
        return (
            API_KEY_PATH.is_file()
            and bool(
                API_KEY_PATH
                .read_text()
                .strip()
            )
        )

    except OSError:
        return False


def get_catalog_url():
    settings = get_settings()

    return (
        f'{settings["scheme"]}://'
        f'{settings["host"]}:'
        f'{settings["port"]}'
        "/api/catalog-mirror/download"
    )
