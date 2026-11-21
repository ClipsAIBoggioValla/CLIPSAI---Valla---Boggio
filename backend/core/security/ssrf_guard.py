from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger("clipsai.ssrf")

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

# Hostnames que siempre apuntan a metadatos/servicios internos: bloqueados por
# literal, ANTES de resolver DNS (issue #112).
_HOSTNAMES_BLOQUEADOS = frozenset({"localhost", "metadata.google.internal"})

# IP literal del IMDS de las nubes (AWS/GCP/Azure): se valida por literal para
# no depender de la resolución DNS.
_IMDS_LITERAL = "169.254.169.254"

# Propiedades de ipaddress que marcan rangos no enrutables (regla BoolOp: la
# cadena `or` de 5 operandos equivalía a CC 5; `any()` + tuple la baja a CC 2).
_PROTECTORAS = ("is_loopback", "is_private", "is_link_local", "is_multicast", "is_reserved")


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
    return _esta_en_rangos_protectores(addr) or _esta_en_cidrs_bloqueados(addr)


def _esta_en_rangos_protectores(addr) -> bool:
    """Loopback, privada, link-local, multicast o reservada = bloqueada."""
    return any(getattr(addr, propiedad) for propiedad in _PROTECTORAS)


def _esta_en_cidrs_bloqueados(addr) -> bool:
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
    _validar_hostname(parsed.hostname)
    return url


def _validar_hostname(hostname: str) -> None:
    """Bloquea hostnames conocidos, el IMDS literal (antes del DNS) e IPs privadas."""
    _validar_hostname_literal(hostname)
    _validar_dns_hostname(hostname)


def _validar_hostname_literal(hostname: str) -> None:
    """Chequeo por literal: sin tocar la red (localhost, metadata y IMDS)."""
    lowered = hostname.lower()
    if lowered in _HOSTNAMES_BLOQUEADOS:
        logger.warning("Hostname bloqueado por el SSRF guard: %s", hostname)
        raise SSRFError(f"Hostname blocked: {hostname}")
    if hostname == _IMDS_LITERAL:
        logger.warning("IMDS bloqueado por el SSRF guard: %s", hostname)
        raise SSRFError(f"{_IMDS_LITERAL} blocked (IMDS)")


def _validar_dns_hostname(hostname: str) -> None:
    """Resuelve DNS y bloquea si alguna IP resultante es privada/IMDS."""
    for ip in _resolve_ips(hostname):
        if is_ip_blocked(ip):
            logger.warning("IP resuelta bloqueada (%s) para host %s", ip, hostname)
            raise SSRFError(f"Resolved IP blocked {ip} for host {hostname} (SSRF guard)")


def assert_safe_url(url: str) -> None:
    validate_url(url)
