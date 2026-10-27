"""Public-only HTTPS fetches with DNS pinning, size caps and no redirects/proxies."""
import ipaddress
import json
import logging
import re
import socket
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

MAX_RESPONSE = 5 * 1024 * 1024
LOGGER = logging.getLogger("pof")


def log_event(event: str, **safe_fields):
    # Call sites pass only identifiers/counts/status, never URL queries, payloads or exceptions.
    LOGGER.info(json.dumps({"event": event, **safe_fields}))


def safe_path(root: Path, name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.(csv|xlsx|json)", name):
        raise ValueError("Unsafe filename")
    target = (root / name).resolve()
    if target.parent != root.resolve():
        raise ValueError("Path outside application directory")
    return target


def validate_url(url: str, allowed_host: str) -> tuple[str, str]:
    try:
        u = urlsplit(url)
        if (u.scheme != "https" or not u.hostname or u.username or u.password or u.fragment
                or u.port not in (None, 443) or u.hostname.lower() != allowed_host.lower()
                or any(c in url for c in ("\\", "\r", "\n", "\t"))):
            raise ValueError("Only allowlisted HTTPS hosts on port 443 are allowed")
        host = u.hostname.encode("idna").decode("ascii")
        addresses = {result[4][0] for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise ValueError("Non-public network destination blocked")
        return host, sorted(addresses)[0]
    except (OSError, UnicodeError):
        raise ValueError("Destination could not be safely resolved") from None


class SafeHTTP:
    def __init__(self, interval: float = 2, transport=None):
        if not 0.5 <= interval <= 60:
            raise ValueError("Request interval must be 0.5–60 seconds")
        self.interval = interval
        self.last = 0.0
        self.transport = transport

    def fetch(self, url: str, host: str, content_types=("application/json", "text/csv"), *, params=None) -> bytes:
        # Authentication parameters are only supported on reviewed, fixed official API hosts.
        if params is not None and host != "api.bestbuy.com":
            raise ValueError("API parameters are restricted to reviewed official endpoints")
        for attempt in range(3):
            hostname, address = validate_url(url, host)
            time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            try:
                with httpx.Client(timeout=httpx.Timeout(20, connect=5), follow_redirects=False,
                                  trust_env=False, transport=self.transport) as client:
                    # Pin the checked IP. Preserve TLS SNI and certificate verification for the original host.
                    with client.stream("GET", httpx.URL(url).copy_with(host=address),
                        headers={"Host": hostname, "User-Agent": "ProductOpportunityFinder/0.1 (bounded research)"},
                        extensions={"sni_hostname": hostname}, params=params) as response:
                        if 300 <= response.status_code < 400:
                            raise ValueError("Redirect blocked; configure the final authorized HTTPS URL")
                        if response.status_code in (401, 403, 429):
                            from pof.live.errors import from_http
                            raise from_http(response.status_code)
                        if response.status_code >= 500 and attempt < 2:
                            time.sleep(2 ** attempt)
                            continue
                        response.raise_for_status()
                        mime = response.headers.get("content-type", "").split(";")[0].strip().lower()
                        if mime not in content_types:
                            raise ValueError("Unexpected response content type")
                        if int(response.headers.get("content-length", "0")) > MAX_RESPONSE:
                            raise ValueError("Response exceeds 5 MiB")
                        body = bytearray()
                        for chunk in response.iter_bytes(65536):
                            body.extend(chunk)
                            if len(body) > MAX_RESPONSE:
                                raise ValueError("Response exceeds 5 MiB")
                        log_event("fetch_complete", status=response.status_code, size=len(body))
                        return bytes(body)
            except httpx.HTTPError:
                if attempt == 2:
                    raise ValueError("Network request failed; check authorized endpoint and connectivity") from None
                time.sleep(2 ** attempt)
        raise ValueError("Request failed after bounded retries")


def spreadsheet_safe(value):
    if isinstance(value, str):
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
        if value.lstrip().startswith(("=", "+", "-", "@")):
            value = "'" + value
        return value[:32700]
    return value
