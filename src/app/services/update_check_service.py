from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings


GITHUB_RELEASES_API_URL = "https://api.github.com/repos/xinghenLuyus/wg-free-mesh/releases"
GITHUB_RELEASES_PAGE_URL = "https://github.com/xinghenLuyus/wg-free-mesh/releases"
UPDATE_CHECK_TTL = timedelta(hours=1)
VERSION_PATTERN = re.compile(r"^v?(?P<core>\d+\.\d+\.\d+)(?:-rc\.(?P<rc>\d+))?$")


@dataclass(frozen=True)
class ParsedVersion:
    major: int
    minor: int
    patch: int
    rc: int | None

    @property
    def key(self) -> tuple[int, int, int, int, int]:
        return self.major, self.minor, self.patch, 1 if self.rc is None else 0, self.rc or 0

    @property
    def core(self) -> tuple[int, int, int]:
        return self.major, self.minor, self.patch

    @property
    def is_stable(self) -> bool:
        return self.rc is None


class SystemUpdateCheckService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._checked_at: datetime | None = None
        self._payload: dict[str, object] = self._empty_payload()

    def get_status(self) -> dict[str, object]:
        with self._lock:
            if self._checked_at is not None and datetime.now(timezone.utc) - self._checked_at < UPDATE_CHECK_TTL:
                return dict(self._payload)
        payload = self._check_latest_release()
        with self._lock:
            self._checked_at = datetime.now(timezone.utc)
            self._payload = payload
            return dict(self._payload)

    def _check_latest_release(self) -> dict[str, object]:
        current_version = settings.app_version
        current = _parse_version(current_version)
        if current is None:
            return self._empty_payload(current_version=current_version)

        try:
            releases = _fetch_releases()
        except (HTTPError, URLError, TimeoutError, ValueError):
            return self._empty_payload(current_version=current_version)

        latest: dict[str, object] | None = None
        latest_key: tuple[int, int, int, int, int] | None = None
        for release in releases:
            tag_name = str(release.get("tag_name") or "")
            parsed = _parse_version(tag_name)
            if parsed is None or not _is_update_candidate(current, parsed):
                continue
            if latest_key is None or parsed.key > latest_key:
                latest = release
                latest_key = parsed.key

        if latest is None:
            return self._empty_payload(current_version=current_version)

        tag_name = str(latest.get("tag_name") or "").lstrip("v")
        html_url = str(latest.get("html_url") or GITHUB_RELEASES_PAGE_URL)
        return {
            "has_update": True,
            "current_version": current_version,
            "latest_version": tag_name,
            "is_prerelease": bool(latest.get("prerelease")),
            "release_url": html_url,
            "name": str(latest.get("name") or tag_name),
            "published_at": str(latest.get("published_at") or ""),
        }

    @staticmethod
    def _empty_payload(current_version: str | None = None) -> dict[str, object]:
        return {
            "has_update": False,
            "current_version": current_version or settings.app_version,
            "latest_version": "",
            "is_prerelease": False,
            "release_url": "",
            "name": "",
            "published_at": "",
        }


def _fetch_releases() -> list[dict[str, object]]:
    request = Request(
        GITHUB_RELEASES_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"WG-Free-Mesh/{settings.app_version}",
        },
    )
    with urlopen(request, timeout=8) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("GitHub releases response is not a list")
    return [item for item in data if isinstance(item, dict)]


def _parse_version(version: str) -> ParsedVersion | None:
    match = VERSION_PATTERN.match(version.strip())
    if not match:
        return None
    major, minor, patch = (int(part) for part in match.group("core").split("."))
    rc_text = match.group("rc")
    if rc_text is None:
        return ParsedVersion(major=major, minor=minor, patch=patch, rc=None)
    return ParsedVersion(major=major, minor=minor, patch=patch, rc=int(rc_text))


def _is_update_candidate(current: ParsedVersion, candidate: ParsedVersion) -> bool:
    if current.is_stable:
        return candidate.is_stable and candidate.key > current.key
    if candidate.is_stable:
        return candidate.core >= current.core
    return candidate.key > current.key


system_update_check_service = SystemUpdateCheckService()
