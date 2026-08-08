"""Guards for outbound requests made from user-provided URLs.

URLs submitted to scan endpoints must never cause the service to connect to a
loopback, private, link-local, or otherwise non-public address.  Validation is
performed before every request and before each redirect is followed.
"""
from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse


MAX_REDIRECTS = 10
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


class UnsafeURL(ValueError):
    """Raised when a URL could resolve to a non-public network address."""


def resolve_hostname(hostname: str) -> set[str]:
    """Resolve all addresses for *hostname* instead of trusting one result."""
    try:
        results = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURL(f"Unable to resolve URL hostname: {hostname}") from exc

    addresses = {result[4][0] for result in results}
    if not addresses:
        raise UnsafeURL(f"URL hostname did not resolve to an address: {hostname}")
    return addresses


def _address_is_public(address: str) -> bool:
    """Return true only for globally routable IPv4 or IPv6 addresses."""
    try:
        return ipaddress.ip_address(address).is_global
    except ValueError as exc:
        raise UnsafeURL(f"Hostname resolved to an invalid address: {address}") from exc


def validate_public_url(url: str) -> str:
    """Validate an HTTP(S) URL and every address its hostname resolves to.

    A hostname is permitted only when all of its resolved addresses are global.
    Rejecting mixed public/private DNS results prevents the usual DNS-rebinding
    path where a public-looking host has an internal address in its answer set.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURL("Only http and https URLs may be fetched")
    if not parsed.hostname:
        raise UnsafeURL("URL must include a hostname")

    hostname = parsed.hostname
    try:
        addresses: Iterable[str] = {str(ipaddress.ip_address(hostname))}
    except ValueError:
        addresses = resolve_hostname(hostname)

    unsafe_addresses = [address for address in addresses if not _address_is_public(address)]
    if unsafe_addresses:
        raise UnsafeURL(
            f"URL hostname resolves to a non-public address: {', '.join(unsafe_addresses)}"
        )
    return url


async def get_with_validated_redirects(client, url: str, *, headers: dict | None = None):
    """GET a URL while validating the initial target and each redirect target.

    The caller must construct ``client`` with ``follow_redirects=False``.  The
    explicit redirect loop ensures a redirect is checked before the next HTTP
    request is made, rather than after an HTTP client has already followed it.
    """
    current_url = url
    redirect_chain: list[str] = []

    for redirect_count in range(MAX_REDIRECTS + 1):
        validate_public_url(current_url)
        if current_url not in redirect_chain:
            redirect_chain.append(current_url)

        if headers is None:
            response = await client.get(current_url)
        else:
            response = await client.get(current_url, headers=headers)

        status_code = getattr(response, "status_code", None)
        response_headers = getattr(response, "headers", {}) or {}
        location = response_headers.get("location")
        if status_code in REDIRECT_STATUS_CODES and location:
            if redirect_count == MAX_REDIRECTS:
                raise UnsafeURL("Redirect limit exceeded")
            current_url = urljoin(current_url, location)
            # Check the redirect target now, before issuing another request.
            validate_public_url(current_url)
            continue

        # HTTPX responses should have no history because redirects are disabled.
        # Keeping this validation makes the guard safe with alternative clients
        # and validates a final URL reported by a transport or test double.
        for historic_response in getattr(response, "history", []):
            historic_url = str(getattr(historic_response, "url", current_url))
            validate_public_url(historic_url)
            if historic_url not in redirect_chain:
                redirect_chain.append(historic_url)

        final_url = str(getattr(response, "url", current_url))
        validate_public_url(final_url)
        if final_url not in redirect_chain:
            redirect_chain.append(final_url)
        return response, redirect_chain

    raise UnsafeURL("Redirect limit exceeded")
