"""Interface for ``python -m fastcs_rtc6``."""

from fastcs.launch import launch

from fastcs_rtc6.controller import RtcController

from . import __version__

__all__ = ["main"]


def main() -> None:
    launch(RtcController, version=__version__)


if __name__ == "__main__":
    main()
