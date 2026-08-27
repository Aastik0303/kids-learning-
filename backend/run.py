"""Start the learning server on port 8008, reachable however the browser asks.

    python run.py            (from backend/)
    python run.py --reload

`uvicorn app.main:app --port 8008` works too, and is what the README has always
said. This script exists because that command has two Windows-shaped problems
that cost an afternoon each time somebody hits them.

**1. `localhost` is two addresses, and uvicorn only binds one.**

`uvicorn --port 8008` binds `127.0.0.1` - IPv4 only. On this machine `localhost`
resolves to `::1` *first* and `127.0.0.1` second, and the web app is configured
to call `http://localhost:8008`. Chrome usually falls back to IPv4 fast enough
that nobody notices, and sometimes it does not - and when it does not, the page
says "We could not reach the learning server" while the server sits there
answering `curl` perfectly. `--host ::` is not the fix either: on Windows that
binds IPv6 *only*, and then `127.0.0.1:8008` stops working instead.

The fix is one socket that answers both, which is what `dualstack_ipv6=True`
does. Every spelling of the address now reaches the same server:

    http://localhost:8008     http://127.0.0.1:8008     http://[::1]:8008

**2. The Proactor event loop shouts when a browser hangs up.**

Windows' default asyncio loop logs a full traceback -
`ConnectionResetError: [WinError 10054]` out of
`_ProactorBasePipeTransport._call_connection_lost` - every time a client drops a
connection without closing it politely. Browsers do that constantly: speculative
connections, a cancelled fetch, a reloaded tab. Nothing is wrong and nothing
failed, but the log fills with tracebacks and the next real error is impossible
to find in them, which is how a "cannot reach the server" report turns into an
afternoon. One logging filter drops that exact exception and nothing else.
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys

import uvicorn


PORT = 8008
HOST = "::"  # dual-stack: this one socket answers IPv4 and IPv6 alike


class _DropClientHangups(logging.Filter):
    """Drop the traceback asyncio logs when a browser hangs up mid-connection.

    Windows' Proactor loop raises `ConnectionResetError [WinError 10054]` out of
    `_ProactorBasePipeTransport._call_connection_lost` whenever a peer closes a
    socket without the polite handshake. Browsers do that constantly - a
    speculative connection they decided not to use, a cancelled `fetch`, a
    reloaded tab - and every one of them printed a full traceback.

    Nothing failed, no request was lost, and no user ever saw anything. What it
    cost was the log: a real error was invisible in the noise, which is exactly
    how a "cannot reach the server" report ends up taking an afternoon.

    Only this one exception, only from that one place. Anything else asyncio has
    to say still gets through, and swapping the whole event loop to avoid it is
    not worth it - `WindowsSelectorEventLoopPolicy` is deprecated in 3.14 and
    goes away in 3.16.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not record.exc_info:
            return True
        error = record.exc_info[1]
        if isinstance(error, ConnectionResetError) and getattr(error, "winerror", None) == 10054:
            return False
        return True


def _quiet_client_hangups() -> None:
    """Stop a browser closing a socket from looking like a server fault."""
    if sys.platform == "win32":
        logging.getLogger("asyncio").addFilter(_DropClientHangups())


def _dualstack_socket(host: str, port: int) -> socket.socket:
    """One listening socket that answers on both IP families.

    Falls back to a plain IPv4 socket on a machine whose network stack cannot do
    it - better a server on `127.0.0.1` than no server at all.
    """
    if socket.has_dualstack_ipv6():
        return socket.create_server(
            (host, port), family=socket.AF_INET6, dualstack_ipv6=True, reuse_port=False
        )

    print("This machine cannot do dual-stack sockets; binding IPv4 only.")
    return socket.create_server(("0.0.0.0", port), reuse_port=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Saksham IQ learning server.")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart on code changes. Rebinds the port itself, so it cannot "
        "share the dual-stack socket - IPv4 only while it is on.",
    )
    args = parser.parse_args()

    _quiet_client_hangups()

    if args.reload:
        # The reloader spawns a child process, and a socket made here cannot be
        # handed to it. Reload is a while-you-are-editing convenience, so take
        # the IPv4-only bind and say what that means for `localhost`.
        print(
            f"Reload is on, so this binds 127.0.0.1:{args.port} only.\n"
            f"If the web app cannot reach it, use http://127.0.0.1:{args.port} "
            "or run without --reload."
        )
        uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, reload=True)
        return 0

    listener = _dualstack_socket(HOST, args.port)
    print(
        f"Learning server on port {args.port} - reachable at all of:\n"
        f"  http://localhost:{args.port}\n"
        f"  http://127.0.0.1:{args.port}\n"
        f"  http://[::1]:{args.port}"
    )

    server = uvicorn.Server(uvicorn.Config("app.main:app", log_level="info"))
    server.run(sockets=[listener])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
