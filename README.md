[![CI](https://github.com/armin306/fastcs-rtc6/actions/workflows/ci.yml/badge.svg)](https://github.com/armin306/fastcs-rtc6/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/armin306/fastcs-rtc6/branch/main/graph/badge.svg)](https://codecov.io/gh/armin306/fastcs-rtc6)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# fastcs_rtc6

FastCS IOC for the ScanLab RTC6 Ethernet laser controller

Source          | <https://github.com/armin306/fastcs-rtc6>
:---:           | :---:
Docker          | `docker run ghcr.io/armin306/fastcs-rtc6:latest`
Releases        | <https://github.com/armin306/fastcs-rtc6/releases>

# updating the bindings module

To update the bindings, in the devcontainer and with the virtual env activated, execute:

```bash
cd src/fastcs_rtc6/bindings
mkdir build # if necessary
cd build
cmake ..
make
cd ../../../..
pybind11-stubgen fastcs_rtc6.bindings.rtc6_bindings -o src
ruff format .
```

# developing in the container over ssh

At diamond the default devcontainer settings result in some permission issues when run over ssh, but you can build the container and develop in it manually

manually build the container with `podman build -t fastcs-rtc6-dev --target=developer .`
and run it with `podman run -it --net=host --security-opt=label=disable --mount=type=bind,source=/scratch/<fedID>/fastcs-rtc6/,destination=/workspace fastcs-rtc6-dev`
then connect vscode to the laser lab workstation with `remote:ssh` and attach to the running container from the `remote:containers` view
the first time for a running container you will need to install the relevant extensions, run `pip install -e .[dev]`, and `src/fastcs_rtc6/install_library.sh`
when everything is set up, `test_connect()` from `test_bindings.py` should pass, and `./rebuild_bindings.sh` should execute cleanly

you may need/want to add the following to the C++ extension include path for better IDE support:
```
${workspaceFolder}/**
/venv/lib/python3.11/site-packages/pybind11/include/
/usr/include/python3.11
/usr/include
```

# notes

- fastcs doesn't completely work for python 3.12 but fails silently so this project will need to be moved to 3.11
