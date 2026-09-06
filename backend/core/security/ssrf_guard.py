from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


BLOCKED_CIDRS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]


class SSRFError(ValueError):
    pass


def _resolve_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise SSRFError(f"DNS resolution failed for {hostname}: {e}") from e
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for _, _, _, _, sockaddr in infos:
        try:
            ips.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue
    return ips


def is_ip_blocked(ip: str | ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    addr = ipaddress.ip_address(ip) if isinstance(ip, str) else ip
    if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_multicast or addr.is_reserved:
        return True
    for net in BLOCKED_CIDRS:
        if addr in net:
            return True
    return False


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SSRFError(f"Scheme not allowed: {parsed.scheme}")
    if not parsed.hostname:
        raise SSRFError("URL without hostname")
    if parsed.hostname.lower() in {"localhost", "metadata.google.internal"}:
        raise SSRFError(f"Hostname blocked: {parsed.hostname}")
    for ip in _resolve_ips(parsed.hostname):
        if is_ip_blocked(ip):
            raise SSRFError(f"Resolved IP blocked {ip} for host {parsed.hostname} (SSRF guard)")
    if parsed.hostname == "169.254.169.254":
        raise SSRFError("169.254.169.254 blocked (IMDS)")
    return url


def assert_safe_url(url: str) -> None:
    validate_url(url)
