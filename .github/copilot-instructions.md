# AI Coding Instructions for fastcs-rtc6

## Project Overview

**fastcs-rtc6** is a FastCS IOC (EPICS Input/Output Controller) wrapping the ScanLab RTC6 Ethernet laser controller. It combines Python (device layer, controllers) with C++ bindings (low-level hardware communication).

### Architecture Layers

- **Bindings Layer** (`src/fastcs_rtc6/bindings/`): C++ pybind11 wrappers around proprietary RTC6 library
- **Controller Layer** (`src/fastcs_rtc6/controller/`): FastCS Controllers/sub-controllers managing EPICS attributes and hardware commands
- **Device Layer** (`src/fastcs_rtc6/device.py`): Ophyd-async StandardReadable devices exposing EPICS signals
- **Planning Layer** (`src/fastcs_rtc6/cut_shapes.py`, `plan_stubs.py`): Bluesky plans for laser cut shapes

### Key Dependencies

- **fastcs[epicsca] ~0.14.2**: FastCS framework for IOC infrastructure (the CA transport is a separate extra as of fastcs 0.14)
- **ophyd-async**: Async device abstraction for beamline hardware
- **bluesky**: Experimental orchestration and planning
- **pybind11**: C++ to Python bindings

## Build & Development Workflow

### C++ Bindings Updates

When modifying C++ bindings (rtc6_bindings.cpp/pyi), rebuild using:

```bash
cd src/fastcs_rtc6/bindings/build
cmake ..
make
cd ../../../..
pybind11-stubgen fastcs_rtc6.bindings.rtc6_bindings -o src
ruff format .
```

The stub generator creates `rtc6_bindings.pyi` (do NOT edit manually).

### Running the IOC

```bash
fastcs-rtc6 run fastcs.yaml
```

Config-driven since the fastcs 0.14 migration (`fastcs.launch.launch()`) - there's no more `ioc <prefix> <box_ip> ...` CLI. Connection/hardware options (box IP, program/correction file paths, retry behaviour) live in `fastcs.yaml` under the controller entry, mapped onto `RtcControllerOptions` in `rtc_controller.py`. The entry's `id:` sets the live PV prefix (see Fixing EPICS Prefix Issues below).

### Test Requirements

- Tests requiring proprietary RTC6 library are marked `@pytest.mark.needs_librtc6` - exclude with `-m "not needs_librtc6"`
- Run full suite via: `tox -p` (defined in pyproject.toml, runs pytest, lint, docs in parallel)
- Test utilities in `tests/conftest.py` (check for shared fixtures)

### Python Version Constraint

**Python 3.11 only** - no longer a fastcs limitation (fastcs 0.14.2 supports 3.11-3.14, confirmed via fastcs-carbide's CI matrix). The constraint now is the compiled bindings: `rtc6_bindings.cpython-311-*.so` is built for CPython 3.11 specifically. Targeting a newer Python means rebuilding the bindings for it (see C++ Bindings Updates) as well as bumping `requires-python`/classifiers in pyproject.toml.

## Core Patterns & Conventions

### EPICS Attributes & Handlers

Controllers use fastcs's `AttributeIO`/`AttributeIORef` system (fastcs 0.14+; the old `Sender`/`Updater` handler protocol and `SubController` - folded into `Controller` - are gone). `RtcControlSettings` shares one `RtcSettingsIO` across all its attributes, dispatching per-attribute via a `set_fn` callable on each attribute's `io_ref`:

```python
@dataclass
class RtcSettingsIORef(AttributeIORef):
    set_fn: Callable[["RtcControlSettings", Any], None] | None = None

class RtcSettingsIO(AttributeIO[Any, RtcSettingsIORef]):
    async def send(self, attr, value):
        attr.io_ref.set_fn(self.controller, value)  # Custom logic when attribute written
```

Sub-controllers still inherit `RtcConnection` via `ConnectedSubController`, registered with `add_sub_controller(path_segment, instance)` (not `register_sub_controller`). Watch for `Controller.__setattr__` auto-registering any `BaseController` assigned via `self.x = ...` as a sub-controller under that name - `RtcController` bypasses this for `_info_controller` via `object.__setattr__`.

### Ophyd-Async Device Pattern

Devices wrap EPICS signals, exposing Bluesky-compatible interfaces:

```python
class Rtc6ControlSettings(StandardReadable):
    def __init__(self, prefix: str = "CONTROL:"):
        with self.add_children_as_readables():
            self.laser_mode = epics_signal_rw(str, prefix + "LaserMode")
```

Nested classes (e.g., `Rtc6List.AddArc`) mirror nested EPICS hierarchies.

### C++ Function Wrapping

Bindings expose low-level RTC6 API directly:

- `rtc6.connect()`, `rtc6.close()`, `rtc6.check_connection()`
- `rtc6.add_line_to(x, y)`, `rtc6.add_arc_to(x, y, angle)`
- `rtc6.get_card_info()` returns CardInfo dataclass
- `rtc6.get_last_error()` / `get_error_string()` for error handling

### Bluesky Plans

Cut shape execution via Bluesky plans using device `.trigger()`:

```python
def draw_polygon(rtc: Rtc6Eth, shape):
    # shape: list of (x, y, mark_enabled) tuples
    yield from bps.open_run()
    # ... add geometry to list, execute_list trigger
```

## Testing & Debugging

### Unit Test Organization

- `test_bindings.py`: Direct binding function tests (marked `needs_librtc6`)
- `test_cli.py`: CLI/import tests
- Fixtures in `conftest.py` - check before creating new ones

### Connection Testing

The README notes: `test_connect()` from `test_bindings.py` must pass for hardware integration.

### Type Checking

`pyright` in standard mode enabled; `reportMissingImports=false` (imported modules lack stubs).

## Common Tasks

### Adding Hardware Commands

1. Add C++ binding in `rtc6_bindings.cpp` with pybind11 definition
2. Update `rtc6_bindings.pyi` stub or regenerate with pybind11-stubgen
3. Create FastCS attribute + handler in `controller/rtc_controller.py`
4. Wrap in ophyd device in `device.py`

### Fixing EPICS Prefix Issues

The IOC's live PV prefix comes from `fastcs.yaml`'s `controllers[].id` (currently `LA18L-EA-RTC6-01` - Diamond's EPICS-gateway-compatible naming; a bare prefix like the old `RTC6ETH:` won't pass the gateway's regex), not a Python-level default. The ophyd-async `Rtc6Eth` device's `prefix` constructor default (`device.py`) must be kept in sync with it manually. Check:

- `fastcs.yaml`'s `id:` vs `Rtc6Eth.__init__`'s `prefix` default in `device.py`
- FastCS controller attribute groups in `rtc_controller.py`

### Debugging Bindings

Cannot directly inspect C++ behavior from Python tests - use logging in C++ or test via EPICS PVs.

## Project References

- **Source**: https://github.com/armin306/fastcs-rtc6
- **Container**: `ghcr.io/armin306/fastcs-rtc6:latest`
- **RTC6 Manual**: Referenced in code comments (e.g., "manual page 314")
