from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def is_public_http_url(url: str) -> bool:
    """True only if url is http(s) and its host resolves to a public IP -
    blocks localhost, private ranges (10.x/172.16-31.x/192.168.x), and
    link-local/cloud-metadata addresses (169.254.x.x) before the server
    ever makes a request to a user-supplied endpoint.

    This checks the resolved IP at validation/use time, not full
    DNS-rebinding protection (an attacker-controlled DNS record could
    theoretically resolve differently between check and connect) - out of
    scope for this app's threat model, but not a complete guarantee against
    a sophisticated attacker.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        hostname = parsed.hostname
        if not hostname or hostname.lower() == 'localhost':
            return False
        resolved = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(resolved)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified)
    except Exception:
        return False
