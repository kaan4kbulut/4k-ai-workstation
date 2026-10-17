"""Ek API harcaması için ortak, adresi ayrıştıran izin politikası."""

from __future__ import annotations

import ipaddress
import math
from urllib.parse import urlsplit


def is_local_endpoint(base_url: str) -> bool:
    try:
        parsed = urlsplit(base_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        if parsed.query or parsed.fragment:
            return False
        parsed.port  # Geçersiz portları da reddet.
        host = parsed.hostname.lower()
        if host in {"localhost", "0.0.0.0"}:
            return True
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, AttributeError):
        return False


def is_free_openrouter_endpoint(base_url: str, model: str) -> bool:
    try:
        parsed = urlsplit(base_url.strip())
        return (
            parsed.scheme == "https"
            and parsed.hostname == "openrouter.ai"
            and parsed.port in {None, 443}
            and parsed.username is None
            and parsed.password is None
            and parsed.path.rstrip("/") == "/api/v1"
            and not parsed.query
            and not parsed.fragment
            and bool(model.strip()[:-5])
            and model.strip().endswith(":free")
            and not any(c.isspace() for c in model.strip())
        )
    except (ValueError, AttributeError):
        return False


def is_zero_cost_endpoint(base_url: str, model: str, cost: float = 0.0) -> bool:
    try:
        declared_cost = float(cost)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(declared_cost) or declared_cost != 0.0:
        return False
    return is_local_endpoint(base_url) or is_free_openrouter_endpoint(base_url, model)
