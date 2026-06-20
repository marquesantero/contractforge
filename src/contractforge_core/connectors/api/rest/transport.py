"""HTTP transport helpers for the bounded REST connector."""

from __future__ import annotations

import urllib.request


def open_request(request: urllib.request.Request, *, timeout: int):
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=timeout)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(f"REST API source refused a redirect to {newurl}")
