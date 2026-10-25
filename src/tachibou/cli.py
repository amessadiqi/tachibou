"""Command line interface."""

from __future__ import annotations

import argparse
import sys

import uvicorn

from tachibou import __version__
from tachibou.app import create_app
from tachibou.config import DEFAULT_HOST, DEFAULT_PORT, ConfigError, get_settings, validate_port

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tachibou",
        description="Local dashboard for managing independent automations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Start the local web application.")
    start.add_argument(
        "--host",
        default=None,
        help=f"Bind address. Defaults to {DEFAULT_HOST}.",
    )
    start.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Bind port. Defaults to {DEFAULT_PORT}.",
    )
    start.add_argument(
        "--reload",
        action="store_true",
        help="Restart the server when Python code changes.",
    )

    subparsers.add_parser("version", help="Print the installed version.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            print(__version__)
            return 0
        if args.command == "start":
            settings = get_settings()
            start_server(
                args.host or settings.host,
                settings.port if args.port is None else args.port,
                reload=args.reload,
            )
            return 0
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 2


def start_server(host: str, port: int, *, reload: bool = False) -> None:
    validate_port(port)
    if host not in _LOOPBACK_HOSTS:
        print(
            "Warning: Tâchibou is a local tool. Binding to a non-loopback address is unsupported.",
            file=sys.stderr,
        )
    print(f"Tâchibou {__version__} listening on http://{host}:{port}", flush=True)
    if reload:
        uvicorn.run(
            "tachibou.app:create_app",
            factory=True,
            host=host,
            port=port,
            reload=True,
        )
        return
    uvicorn.run(create_app, factory=True, host=host, port=port)


if __name__ == "__main__":
    raise SystemExit(main())
