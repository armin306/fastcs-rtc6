import asyncio
import enum
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from fastcs.attributes import AttributeIO, AttributeIORef, AttrR, AttrRW, AttrW
from fastcs.controllers import Controller
from fastcs.datatypes import Bool, Enum, Float, Int, String
from fastcs.methods import command

from fastcs_rtc6.bindings import rtc6_bindings as rtc6
from fastcs_rtc6.controller.rtc_connection import RtcConnection

LOGGER = logging.getLogger(__name__)


class ConnectedSubController(Controller):
    def __init__(self, conn: RtcConnection) -> None:
        super().__init__()
        self._conn = conn


class RtcInfoController(ConnectedSubController):
    firmware_version = AttrR(Int(), group="Information")
    serial_number = AttrR(Int(), group="Information")
    ip_address = AttrR(String(), group="Information")
    # fastcs 0.14 dropped Bool's znam/onam kwargs, but the labels this
    # attribute wants ("False"/"True") are Bool's own defaults, so there is
    # nothing left to configure here.
    is_acquired = AttrR(Bool(), group="Information")

    async def proc_cardinfo(self) -> None:
        info = self._conn.get_card_info()
        await asyncio.gather(
            self.firmware_version.update(info.firmware_version),
            self.serial_number.update(info.serial_number),
            self.ip_address.update(info.ip_address),
            self.is_acquired.update(info.is_acquired),
        )


class LaserMode(enum.StrEnum):
    """Mirrors the ScanLab bindings' ``LaserMode`` enum (page 645 of the
    manual) as a ``StrEnum`` so it can back a fastcs ``Enum`` attribute -
    the bindings' own pybind11 enum isn't a Python ``Enum`` subclass."""

    CO2 = "CO2"
    YAG1 = "YAG1"
    YAG2 = "YAG2"
    YAG3 = "YAG3"
    LASER4 = "LASER4"
    YAG5 = "YAG5"
    LASER6 = "LASER6"


def _passthrough(
    fn: Callable[[Any], None],
) -> Callable[["RtcControlSettings", Any], None]:
    """Wrap a bindings call that only needs the raw put value."""

    def set_fn(controller: "RtcControlSettings", value: Any) -> None:
        fn(value)

    return set_fn


def _trigger(
    fn: Callable[[], None],
) -> Callable[["RtcControlSettings", Any], None]:
    """Wrap a zero-argument bindings call, ignoring the AttrW's put value.

    ``list_nop``/``save_and_restart_timer`` take no argument in the bindings
    despite being wired to writable ``Int`` PVs - any put just triggers the
    action. The original 0.8 handler was an untyped ``Callable`` and called
    these with the put value regardless, which would have raised
    ``TypeError`` at the C-binding call on any real put.
    """

    def set_fn(controller: "RtcControlSettings", value: Any) -> None:
        fn()

    return set_fn


def _set_laser_mode(controller: "RtcControlSettings", value: LaserMode) -> None:
    rtc6.set_laser_mode(value.value)


def _set_laser_pulses(controller: "RtcControlSettings", value: str) -> None:
    half_period, pulse_length = map(int, value.split(","))
    rtc6.set_laser_pulses(half_period, pulse_length)


def _set_wobbel_mode(controller: "RtcControlSettings", value: str) -> None:
    # transversal, longitudinal, freq, mode
    parts = value.split(",")
    rtc6.set_wobbel_mode(int(parts[0]), int(parts[1]), float(parts[2]), int(parts[3]))


def _set_sky_writing_para(controller: "RtcControlSettings", value: str) -> None:
    # timelag, laserOnShift, nPrev, nPost
    parts = value.split(",")
    rtc6.set_sky_writing_para_list(
        float(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    )


def _set_angle_list(controller: "RtcControlSettings", value: str) -> None:
    # headNo, angle, at_once
    parts = value.split(",")
    rtc6.set_angle_list(int(parts[0]), float(parts[1]), int(parts[2]))


def _set_offset_xyz_list(controller: "RtcControlSettings", value: str) -> None:
    # headNo, x, y, z, at_once
    parts = value.split(",")
    rtc6.set_offset_xyz_list(
        int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
    )


def _set_scanahead_laser_shifts(controller: "RtcControlSettings", value: str) -> None:
    # dLasOn, dLasOff
    parts = value.split(",")
    rtc6.set_scanahead_laser_shifts_list(int(parts[0]), int(parts[1]))


def _set_scanahead_line_params(controller: "RtcControlSettings", value: str) -> None:
    # cornerScale, endScale, accScale
    parts = value.split(",")
    rtc6.set_scanahead_line_params_list(int(parts[0]), int(parts[1]), int(parts[2]))


def _set_laser_delays(controller: "RtcControlSettings", value: str) -> None:
    # laser_on_delay, laser_off_delay
    parts = value.split(",")
    rtc6.set_laser_delays(int(parts[0]), int(parts[1]))


def _set_scanner_delays(controller: "RtcControlSettings", value: int) -> None:
    # set_scanner_delays(jump, mark, polygon) in 10us increments - all three
    # need setting at once, so recompute from all three attrs' cached values
    # whenever any one of them is written.
    rtc6.set_scanner_delays(
        controller.jump_delay.get(),
        controller.mark_delay.get(),
        controller.polygon_delay.get(),
    )


@dataclass
class RtcSettingsIORef(AttributeIORef):
    set_fn: Callable[["RtcControlSettings", Any], None] | None = None


class RtcSettingsIO(AttributeIO[Any, RtcSettingsIORef]):
    """Writes RTC6 settings via the bindings call named per-attribute in
    ``RtcSettingsIORef.set_fn`` - one shared IO per ``RtcControlSettings``,
    since a few settings (jump/mark/polygon delay) need to combine sibling
    attributes into a single bindings call."""

    def __init__(self, controller: "RtcControlSettings") -> None:
        super().__init__()
        self.controller = controller

    async def update(self, attr: AttrR[Any, RtcSettingsIORef]) -> None:
        # The RTC6 bindings expose no getters for these settings; send()
        # mirrors each write into the attribute's own cache instead.
        return

    async def send(self, attr: AttrW[Any, RtcSettingsIORef], value: Any) -> None:
        set_fn = attr.io_ref.set_fn
        assert set_fn is not None, f"{attr} has no set_fn"
        set_fn(self.controller, value)
        if isinstance(attr, AttrR):
            await attr.update(value)


class RtcControlSettings(Controller):
    def __init__(self, conn: RtcConnection) -> None:
        self._conn = conn
        self.io = RtcSettingsIO(self)
        super().__init__(ios=[self.io])

    # Page 645 of the manual
    laser_mode = AttrW(
        Enum(LaserMode),
        group="LaserControl",
        io_ref=RtcSettingsIORef(set_fn=_set_laser_mode),
    )
    laser_control = AttrW(
        Int(),
        group="LaserControl",
        io_ref=RtcSettingsIORef(set_fn=_passthrough(rtc6.set_laser_control)),
    )
    mark_speed = AttrW(
        Float(),
        group="LaserControl",
        io_ref=RtcSettingsIORef(set_fn=_passthrough(rtc6.set_mark_speed_ctrl)),
    )
    jump_speed = AttrW(
        Float(),
        group="LaserControl",
        io_ref=RtcSettingsIORef(set_fn=_passthrough(rtc6.set_jump_speed_ctrl)),
    )
    list_nop = AttrW(
        Int(),
        group="ListProgramming",
        io_ref=RtcSettingsIORef(set_fn=_trigger(rtc6.list_nop)),
    )
    save_restart_timer = AttrW(
        Int(),
        group="ListProgramming",
        io_ref=RtcSettingsIORef(set_fn=_trigger(rtc6.save_and_restart_timer)),
    )
    laser_pulses = AttrW(
        String(),
        group="ListProgramming",
        io_ref=RtcSettingsIORef(set_fn=_set_laser_pulses),
    )
    firstpulse_killer = AttrW(
        Int(),
        group="ListProgramming",
        io_ref=RtcSettingsIORef(set_fn=_passthrough(rtc6.set_firstpulse_killer_list)),
    )
    wobbel_mode = AttrW(
        String(),
        group="ListProgramming",
        io_ref=RtcSettingsIORef(set_fn=_set_wobbel_mode),
    )
    sky_writing_para = AttrW(
        String(),
        group="ListProgramming",
        io_ref=RtcSettingsIORef(set_fn=_set_sky_writing_para),
    )
    angle_list = AttrW(
        String(),
        group="ListProgramming",
        io_ref=RtcSettingsIORef(set_fn=_set_angle_list),
    )
    offset_xyz_list = AttrW(
        String(),
        group="ListProgramming",
        io_ref=RtcSettingsIORef(set_fn=_set_offset_xyz_list),
    )
    scanahead_autodelays = AttrW(
        Int(),
        group="ListProgramming",
        io_ref=RtcSettingsIORef(
            set_fn=_passthrough(rtc6.activate_scanahead_autodelays_list)
        ),
    )
    scanahead_laser_shifts = AttrW(
        String(),
        group="ListProgramming",
        io_ref=RtcSettingsIORef(set_fn=_set_scanahead_laser_shifts),
    )
    scanahead_line_params = AttrW(
        String(),
        group="ListProgramming",
        io_ref=RtcSettingsIORef(set_fn=_set_scanahead_line_params),
    )
    laser_delays = AttrW(
        String(),
        group="LaserControl",
        io_ref=RtcSettingsIORef(set_fn=_set_laser_delays),
    )
    # set_scanner_delays(jump, mark, polygon) in 10us increments
    # need to all be set at once - special handler
    jump_delay = AttrRW(
        Int(),
        group="LaserControl",
        io_ref=RtcSettingsIORef(set_fn=_set_scanner_delays),
    )
    mark_delay = AttrRW(
        Int(),
        group="LaserControl",
        io_ref=RtcSettingsIORef(set_fn=_set_scanner_delays),
    )
    polygon_delay = AttrRW(
        Int(),
        group="LaserControl",
        io_ref=RtcSettingsIORef(set_fn=_set_scanner_delays),
    )


class XYCorrectedConnectedSubController(ConnectedSubController):
    def __init__(
        self, conn: RtcConnection, coordinate_correction_matrix: np.ndarray
    ) -> None:
        super().__init__(conn)
        self.coordinate_correction_matrix = coordinate_correction_matrix

    def correct_xy(self, x: int, y: int) -> tuple[int, int]:
        """Correct for transformations in the laser / oav optics"""
        print(f"Correcting {(x, y)} by {self.coordinate_correction_matrix}")
        corrected = np.matmul(self.coordinate_correction_matrix, [x, y])
        as_ints = (int(corrected[0]), int(corrected[1]))
        print(f"Result: {corrected} => {as_ints}")
        return as_ints


class RtcListOperations(XYCorrectedConnectedSubController):
    list_pointer_position = AttrR(Int(), group="ListInfo")

    class AddJump(XYCorrectedConnectedSubController):
        x = AttrRW(Int(), group="ListOps")
        y = AttrRW(Int(), group="ListOps")

        @command(group="ListOps")
        async def proc(self):
            print("adding jump")
            bindings = self._conn.get_bindings()
            x, y = self.correct_xy(self.x.get(), self.y.get())
            bindings.add_jump_to(x, y)
            print("---")

    class AddArc(XYCorrectedConnectedSubController):
        x = AttrRW(Int(), group="ListOps")
        y = AttrRW(Int(), group="ListOps")
        angle = AttrRW(Float(), group="ListOps")

        @command()
        async def proc(self):
            print("adding arc")
            bindings = self._conn.get_bindings()
            x, y = self.correct_xy(self.x.get(), self.y.get())
            bindings.add_arc_to(x, y, self.angle.get())
            print("---")

    class AddLine(XYCorrectedConnectedSubController):
        x = AttrRW(Int(), group="ListOps")
        y = AttrRW(Int(), group="ListOps")

        @command()
        async def proc(self):
            print("adding line")
            bindings = self._conn.get_bindings()
            bindings.add_line_to(*self.correct_xy(self.x.get(), self.y.get()))
            print("---")

    @command()
    async def init_list(self):
        rtc6 = self._conn.get_bindings()
        rtc6.config_list_memory(10000000, 1)  # Just put everything on list one
        rtc6.init_list_loading(1)

    @command()
    async def end_list(self):
        rtc6 = self._conn.get_bindings()
        rtc6.set_end_of_list()

    @command()
    async def execute_list(self):
        rtc6 = self._conn.get_bindings()
        rtc6.execute_list(1)


@dataclass
class RtcControllerOptions:
    box_ip: str = "172.23.171.209"
    program_file_dir: str = "./rtc6_files/program_files"
    correction_file: str = "./correction_files/D3_10019.ct5"
    coordinate_system_correction_file: str = "./correction_files/coord_transform"
    retry_connect: bool = False


class RtcController(Controller):
    # Type-hinted so callers can reach this sub-controller's own methods
    # (proc_cardinfo) without going through get_sub_controllers()'s base
    # BaseController return type - see the object.__setattr__ note below.
    _info_controller: RtcInfoController

    def __init__(self, options: RtcControllerOptions) -> None:
        super().__init__()
        try:
            self.coordinate_system_transform = np.loadtxt(
                options.coordinate_system_correction_file
            )
        except Exception:
            LOGGER.warning(
                "Failed to open coordinate system transformation file, "
                "defaulting to identity matrix."
            )
            self.coordinate_system_transform = np.array([[1, 0], [0, 1]])
        self._conn = RtcConnection(
            options.box_ip,
            options.program_file_dir,
            options.correction_file,
            options.retry_connect,
        )

        info_controller = RtcInfoController(self._conn)
        self.add_sub_controller("INFO", info_controller)
        # Controller.__setattr__ auto-registers any BaseController assigned
        # via `self.x = ...` as a sub-controller under that attribute's own
        # name - bypass it so `_info_controller` stays a plain reference
        # instead of a second, conflicting registration of the same
        # controller.
        object.__setattr__(self, "_info_controller", info_controller)

        self.add_sub_controller("CONTROL", RtcControlSettings(self._conn))
        list_controller = RtcListOperations(
            self._conn, self.coordinate_system_transform
        )
        self.add_sub_controller("LIST", list_controller)
        list_controller.add_sub_controller(
            "ADDJUMP",
            list_controller.AddJump(self._conn, self.coordinate_system_transform),
        )
        list_controller.add_sub_controller(
            "ADDARC",
            list_controller.AddArc(self._conn, self.coordinate_system_transform),
        )
        list_controller.add_sub_controller(
            "ADDLINE",
            list_controller.AddLine(self._conn, self.coordinate_system_transform),
        )

    async def connect(self) -> None:
        await self._conn.connect()
        await self._info_controller.proc_cardinfo()
        await super().connect()

    async def close(self) -> None:
        await self._conn.close()
