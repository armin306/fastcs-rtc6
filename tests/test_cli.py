import subprocess
import sys

from fastcs_rtc6 import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "fastcs_rtc6", "--version"]
    assert f"RtcController: {__version__}" in subprocess.check_output(cmd).decode()
