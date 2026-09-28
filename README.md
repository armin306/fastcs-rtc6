[![CI](https://github.com/armin306/fastcs-rtc6/actions/workflows/ci.yml/badge.svg)](https://github.com/armin306/fastcs-rtc6/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/armin306/fastcs-rtc6/branch/main/graph/badge.svg)](https://codecov.io/gh/armin306/fastcs-rtc6)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# fastcs_rtc6

FastCS IOC for the ScanLab RTC6 Ethernet laser controller

Source          | <https://github.com/armin306/fastcs-rtc6>
:---:           | :---:
Docker          | `docker run ghcr.io/armin306/fastcs-rtc6:latest`
Releases        | <https://github.com/armin306/fastcs-rtc6/releases>

# running the IOC

```bash
fastcs-rtc6 run fastcs.yaml
```

Config-driven, via [fastcs](https://github.com/DiamondLightSource/FastCS)'s `launch()` - there's no separate `ioc <prefix> <box_ip> ...` command any more. Connection settings (box IP, program/correction file paths, retry behaviour) go under the controller entry in `fastcs.yaml`; its `id:` sets the IOC's PV prefix (currently `LA18L-EA-RTC6-01`, chosen to pass Diamond's EPICS gateways).

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

- Python 3.11 only: not a fastcs limitation any more (fastcs 0.14.2 supports 3.11-3.14), but the compiled bindings (`rtc6_bindings.cpython-311-*.so`) are built for CPython 3.11 specifically - targeting a newer Python means rebuilding them (see "updating the bindings module" above) as well as bumping `requires-python`/classifiers in `pyproject.toml`.
