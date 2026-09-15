"""
cloud.py — Deye Cloud OpenAPI client (https://developer.deyecloud.com).

Auth flow (confirmed against https://eu1-developer.deyecloud.com/v2/api-docs):

    POST {base}/account/token?appId=<appId>        <- appId is a QUERY param, not body
        {"appSecret": ..., "email": ..., "password": <sha256 hex>, "companyId": ...}
     -> {"accessToken", "refreshToken", "expiresIn", "tokenType", "success", "code", "msg"}

Every subsequent call sends `Authorization: Bearer <accessToken>` and returns a
`success` / `code` / `msg` envelope that must be checked before parsing the payload.
"""
import hashlib
import json
import os
import time
from urllib.parse import quote

import requests

from config import (
    CLOUD_APP_ID,
    CLOUD_APP_SECRET,
    CLOUD_BASE_URL,
    CLOUD_COMPANY_ID,
    CLOUD_DEVICE_TYPE,
    CLOUD_EMAIL,
    CLOUD_PASSWORD,
    CLOUD_TIMEOUT,
    CLOUD_TOKEN_CACHE,
)

# Refresh the token when it has less than this long to live (tokens last ~60 days).
TOKEN_REFRESH_MARGIN = 3600

# HTTP statuses that mean "your token is no good" — worth one silent re-auth + retry.
AUTH_STATUSES = (401, 403)

# Business codes/messages that also mean the token went stale mid-flight.
AUTH_HINTS = ("token", "unauthor", "expire", "invalid_grant")


class DeyeCloudError(RuntimeError):
    """A Deye Cloud call failed, either at HTTP level or via the success/code/msg envelope."""

    def __init__(self, message: str, code: str = "", request_id: str = ""):
        self.code = code
        self.request_id = request_id
        detail = f" (code={code})" if code else ""
        detail += f" [requestId={request_id}]" if request_id else ""
        super().__init__(message + detail)


def sha256_hex(password: str) -> str:
    """Deye expects the account password as a lowercase SHA-256 hex digest."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class DeyeCloudClient:
    """Minimal Deye Cloud client: token lifecycle plus the three read endpoints we need."""

    def __init__(
        self,
        base_url: str = CLOUD_BASE_URL,
        app_id: str = CLOUD_APP_ID,
        app_secret: str = CLOUD_APP_SECRET,
        email: str = CLOUD_EMAIL,
        password: str = CLOUD_PASSWORD,
        company_id: str = CLOUD_COMPANY_ID,
        token_cache: str = CLOUD_TOKEN_CACHE,
        timeout: int = CLOUD_TIMEOUT,
    ):
        self.base_url    = base_url.rstrip("/")
        self.app_id      = app_id
        self.app_secret  = app_secret
        self.email       = email
        self.password    = password
        self.company_id  = company_id
        self.token_cache = token_cache
        self.timeout     = timeout

        self._token: str | None = None
        self._expires_at: float = 0.0
        self._session = requests.Session()

    # ── Token handling ─────────────────────────────────────────────────────────

    def _cache_read(self) -> None:
        """Load a previously issued token from disk, if it is still comfortably valid."""
        if not self.token_cache or not os.path.exists(self.token_cache):
            return
        try:
            with open(self.token_cache, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            token = data.get("access_token")
            expires_at = float(data.get("expires_at", 0))
        except (OSError, ValueError, TypeError):
            return  # Corrupt cache is not fatal — just re-authenticate.
        if token and expires_at - time.time() > TOKEN_REFRESH_MARGIN:
            self._token = token
            self._expires_at = expires_at

    def _cache_write(self) -> None:
        """Persist the token so a systemd Restart=always loop doesn't re-auth every few seconds."""
        if not self.token_cache:
            return
        try:
            # Create with 0600 already set. Writing first and chmod'ing after would leave
            # the token briefly readable by any local user (umask is typically 0022).
            fd = os.open(self.token_cache, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"access_token": self._token, "expires_at": self._expires_at}, fh)
            # An existing file keeps its old mode through O_CREAT, so tighten it too.
            os.chmod(self.token_cache, 0o600)
        except OSError as exc:
            print(f"[deye-cloud] Warning: could not write token cache {self.token_cache}: {exc}")

    def _authenticate(self) -> None:
        """Exchange app credentials + account password for a fresh access token."""
        url = f"{self.base_url}/account/token?appId={quote(str(self.app_id), safe='')}"
        payload = {
            "appSecret": self.app_secret,
            "email": self.email,
            "password": sha256_hex(self.password),
            "companyId": self.company_id,
        }
        try:
            resp = self._session.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            body = resp.json()
        except requests.RequestException as exc:
            raise DeyeCloudError(f"Token request failed: {exc}") from exc
        except ValueError as exc:
            raise DeyeCloudError(f"Token response was not JSON: {exc}") from exc

        if not body.get("success", False) or not body.get("accessToken"):
            raise DeyeCloudError(
                body.get("msg") or "Token request rejected",
                str(body.get("code", "")),
                str(body.get("requestId", "")),
            )

        self._token = body["accessToken"]
        try:
            expires_in = int(body.get("expiresIn", 0))
        except (TypeError, ValueError):
            expires_in = 0
        # Fall back to 24h if the server omits expiresIn, so we still refresh eventually.
        self._expires_at = time.time() + (expires_in if expires_in > 0 else 86400)
        self._cache_write()

    def token(self) -> str:
        """Return a valid bearer token, authenticating or refreshing as needed."""
        if self._token is None:
            self._cache_read()
        if self._token is None or self._expires_at - time.time() <= TOKEN_REFRESH_MARGIN:
            self._authenticate()
        return self._token  # type: ignore[return-value]

    def invalidate_token(self) -> None:
        """Drop the in-memory and on-disk token so the next call re-authenticates."""
        self._token = None
        self._expires_at = 0.0
        try:
            if self.token_cache and os.path.exists(self.token_cache):
                os.remove(self.token_cache)
        except OSError:
            pass

    # ── Requests ───────────────────────────────────────────────────────────────

    def _post(self, path: str, payload: dict, _retried: bool = False) -> dict:
        """POST to an authenticated endpoint and unwrap the success/code/msg envelope."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token()}",
        }
        try:
            resp = self._session.post(url, headers=headers, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise DeyeCloudError(f"{path} request failed: {exc}") from exc

        if resp.status_code in AUTH_STATUSES and not _retried:
            self.invalidate_token()
            return self._post(path, payload, _retried=True)

        try:
            resp.raise_for_status()
            body = resp.json()
        except requests.RequestException as exc:
            raise DeyeCloudError(f"{path} returned HTTP {resp.status_code}: {exc}") from exc
        except ValueError as exc:
            raise DeyeCloudError(f"{path} response was not JSON: {exc}") from exc

        if not body.get("success", False):
            msg = str(body.get("msg") or "request rejected")
            code = str(body.get("code", ""))
            if not _retried and any(h in (msg + code).lower() for h in AUTH_HINTS):
                self.invalidate_token()
                return self._post(path, payload, _retried=True)
            raise DeyeCloudError(f"{path}: {msg}", code, str(body.get("requestId", "")))

        return body

    # ── Endpoints ──────────────────────────────────────────────────────────────

    def device_list(self, page: int = 1, size: int = 10) -> list[dict]:
        """
        List devices on the account — the way to discover your inverter's deviceSn.

        Note: on personal (non-organization) accounts this endpoint has been observed to
        reject an otherwise-valid token with code 2101019 "auth invalid token", while
        /account/info, /station/list and /device/latest accept the same token. Callers
        should be ready to fall back to station_list().
        """
        body = self._post("/device/list", {"page": page, "size": size})
        return body.get("deviceList") or []

    def station_list(self, page: int = 1, size: int = 10) -> list[dict]:
        """List stations (plants) on the account."""
        body = self._post("/station/list", {"page": page, "size": size})
        return body.get("stationList") or []

    def measure_points(self, device_sn: str, device_type: str = CLOUD_DEVICE_TYPE) -> list:
        """List the measure-point keys this device can report."""
        body = self._post(
            "/device/measurePoints", {"deviceSn": device_sn, "deviceType": device_type}
        )
        return body.get("measurePoints") or []

    def latest(self, device_sn: str) -> tuple[dict, list[dict], int | None]:
        """
        Fetch the latest data point set for one device.

        Returns:
            (values, raw_items, collection_time) where `values` maps measure-point key
            -> raw string value, `raw_items` is the untouched dataList (key/name/value/unit,
            used by --dump), and `collection_time` is the logger's upload epoch or None.
        """
        body = self._post("/device/latest", {"deviceList": [device_sn]})
        devices = body.get("deviceDataList") or []
        if not devices:
            return {}, [], None

        device = devices[0]
        items = device.get("dataList") or []
        values = {str(item.get("key")): item.get("value") for item in items if item.get("key")}

        collection_time = device.get("collectionTime")
        try:
            collection_time = int(collection_time) if collection_time is not None else None
        except (TypeError, ValueError):
            collection_time = None

        return values, items, collection_time
