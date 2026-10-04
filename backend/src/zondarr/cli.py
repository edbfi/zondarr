"""Serve the application through ``litestar run`` with the Granian plugin."""

import sys

from litestar.cli.main import litestar_group


def main() -> None:
    """Supply the application target while preserving ``litestar run`` options.

    ``zondarr [OPTIONS]`` is ``litestar --app zondarr.app:app run [OPTIONS]``.
    The ``GranianPlugin`` registered in ``zondarr.app`` makes that command start
    Granian.
    """
    litestar_group.main(  # pyright: ignore[reportUnknownMemberType]
        args=["--app", "zondarr.app:app", "run", *sys.argv[1:]],
        prog_name="zondarr",
    )
