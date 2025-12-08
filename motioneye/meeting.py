# Copyright (c) 2025 motionEye contributors
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Meeting backend integration helpers."""

import json
import logging
import os
import re
from typing import Any, Dict, Optional

from tornado import httpclient
from tornado.ioloop import IOLoop, PeriodicCallback

from motioneye import settings
from motioneye.config import additional_config, additional_section

_SETTINGS_FILE_NAME = "meeting.json"
_DEFAULT_SETTINGS: Dict[str, Any] = {
    "device_key": "",
    "token": "",
    "heartbeat_interval": 60,
    "api_base": "https://meeting.ygsoft.fr/api",
}

_settings: Optional[Dict[str, Any]] = None
_heartbeat_callback: Optional[PeriodicCallback] = None


def _settings_path() -> str:
    return os.path.join(settings.CONF_PATH, _SETTINGS_FILE_NAME)


def _load_settings() -> None:
    global _settings

    _settings = dict(_DEFAULT_SETTINGS)
    path = _settings_path()

    if not os.path.exists(path):
        return

    try:
        with open(path) as f:
            loaded = json.load(f)
            if isinstance(loaded, dict):
                _settings.update(loaded)

    except Exception as e:
        logging.error(f"could not read meeting settings from '{path}': {e}")


def _save_settings() -> None:
    path = _settings_path()

    try:
        os.makedirs(settings.CONF_PATH, exist_ok=True)
        with open(path, "w") as f:
            json.dump(_settings, f, sort_keys=True, indent=4)

    except Exception as e:
        logging.error(f"could not save meeting settings to '{path}': {e}")


def _ensure_settings() -> Dict[str, Any]:
    global _settings

    if _settings is None:
        _load_settings()

    return _settings or dict(_DEFAULT_SETTINGS)


def get_settings() -> Dict[str, Any]:
    return dict(_ensure_settings())


def _normalize_interval(value: Any) -> int:
    try:
        interval = int(value)

    except Exception:
        interval = _DEFAULT_SETTINGS["heartbeat_interval"]

    return max(5, interval)


def _update_setting(name: str, value: Any) -> None:
    settings_dict = _ensure_settings()
    settings_dict[name] = value
    _save_settings()
    restart_heartbeat()


def get_device_key() -> str:
    return _ensure_settings().get("device_key", "")


def set_device_key(device_key: str) -> None:
    if device_key is None:
        device_key = ""

    device_key = str(device_key).strip()
    if not re.match(r"^[A-Za-z0-9_-]*$", device_key):
        logging.error("invalid Meeting device key provided")
        return

    _update_setting("device_key", device_key)


def get_token() -> str:
    return _ensure_settings().get("token", "")


def set_token(token: str) -> None:
    if token is None:
        token = ""

    token = str(token).strip()
    _update_setting("token", token)


def get_heartbeat_interval() -> int:
    return _normalize_interval(_ensure_settings().get("heartbeat_interval"))


def set_heartbeat_interval(interval: Any) -> None:
    _update_setting("heartbeat_interval", _normalize_interval(interval))


def get_api_base() -> str:
    return _ensure_settings().get("api_base", _DEFAULT_SETTINGS["api_base"])


def set_api_base(api_base: str) -> None:
    if api_base is None:
        api_base = _DEFAULT_SETTINGS["api_base"]

    api_base = str(api_base).strip() or _DEFAULT_SETTINGS["api_base"]
    if not re.match(r"^https?://", api_base):
        logging.error("invalid Meeting API base URL provided")
        return

    _update_setting("api_base", api_base.rstrip("/"))


async def _send_heartbeat() -> None:
    meeting_settings = get_settings()
    device_key = meeting_settings.get("device_key")
    token = meeting_settings.get("token")
    interval = meeting_settings.get("heartbeat_interval", 0)

    if not device_key or not token or not interval:
        logging.debug("Meeting heartbeat skipped: incomplete configuration")
        return

    api_base = meeting_settings.get("api_base") or _DEFAULT_SETTINGS["api_base"]
    url = f"{api_base}/devices/{device_key}/online"
    payload = json.dumps({"note": "motionEye heartbeat"})
    headers = {
        "Content-Type": "application/json",
        "X-Meeting-Ssh-Token": token,
    }

    request = httpclient.HTTPRequest(
        url=url,
        method="POST",
        body=payload,
        headers=headers,
        request_timeout=15,
        validate_cert=settings.VALIDATE_CERTS,
    )

    try:
        response = await httpclient.AsyncHTTPClient().fetch(request)
        logging.debug(
            "Meeting heartbeat sent: %s %s", response.code, response.reason or "ok"
        )

    except httpclient.HTTPError as e:
        logging.error(f"Meeting heartbeat failed: {e}")

    except Exception as e:  # pragma: no cover - network errors
        logging.error(f"unexpected Meeting heartbeat error: {e}")


def restart_heartbeat() -> None:
    global _heartbeat_callback

    if _heartbeat_callback:
        try:
            _heartbeat_callback.stop()

        except Exception:
            pass

    meeting_settings = get_settings()
    interval_seconds = meeting_settings.get("heartbeat_interval", 0)
    device_key = meeting_settings.get("device_key")
    token = meeting_settings.get("token")

    if not device_key or not token or not interval_seconds:
        _heartbeat_callback = None
        logging.debug("Meeting heartbeat disabled: waiting for credentials and interval")
        return

    interval_ms = _normalize_interval(interval_seconds) * 1000
    _heartbeat_callback = PeriodicCallback(
        lambda: IOLoop.current().spawn_callback(_send_heartbeat), interval_ms
    )
    _heartbeat_callback.start()
    IOLoop.current().spawn_callback(_send_heartbeat)
    logging.info(
        "Meeting heartbeat enabled every %ss for device %s",
        interval_ms / 1000,
        device_key,
    )


def start() -> None:
    _ensure_settings()
    restart_heartbeat()


@additional_section
def meeting():
    return {
        "label": "Meeting backend",
        "description": "Configure Meeting device identity and heartbeat",
        "open": True,
    }


@additional_config
def meeting_device_key():
    return {
        "label": "Meeting device key",
        "description": "Unique device identifier used by the Meeting API.",
        "type": "str",
        "section": "meeting",
        "required": False,
        "get": get_device_key,
        "set": set_device_key,
        "validate": "^[a-z0-9_-]+$",
    }


@additional_config
def meeting_token():
    return {
        "label": "Meeting token",
        "description": "Secret token presented as X-Meeting-Ssh-Token for API calls.",
        "type": "pwd",
        "section": "meeting",
        "required": False,
        "get": get_token,
        "set": set_token,
    }


@additional_config
def meeting_heartbeat_interval():
    return {
        "label": "Heartbeat interval",
        "description": "Seconds between heartbeats sent to the Meeting API.",
        "type": "number",
        "section": "meeting",
        "required": False,
        "unit": "s",
        "min": 5,
        "get": get_heartbeat_interval,
        "set": set_heartbeat_interval,
    }


@additional_config
def meeting_api_base():
    return {
        "label": "Meeting API base URL",
        "description": "Root URL used to reach the Meeting REST API.",
        "type": "str",
        "section": "meeting",
        "required": False,
        "get": get_api_base,
        "set": set_api_base,
    }
