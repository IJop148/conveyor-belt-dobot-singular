import math
import struct
from .message import Message
import struct
import math
import logging
from enum import IntEnum
from threading import RLock
from typing import NamedTuple, Set, Optional
import time
import serial
from serial.tools import list_ports
from collections import deque


MAX_QUEUE_LEN = 32

class CustomPosition(object):
    def __init__(self, x = None, y = None, z = None, r = None):
        self.x = x
        self.y = y
        self.z = z
        self.r = r


class MODE_PTP(IntEnum):

    JUMP_XYZ = 0x00
    MOVJ_XYZ = 0x01
    MOVL_XYZ = 0x02
    JUMP_ANGLE = 0x03
    MOVJ_ANGLE = 0x04
    MOVL_ANGLE = 0x05
    MOVJ_INC = 0x06
    MOVL_INC = 0x07
    MOVJ_XYZ_INC = 0x08
    JUMP_MOVL_XYZ = 0x09


STEP_PER_CIRCLE = 360.0 / 1.8 * 10.0 * 16.0
MM_PER_CIRCLE = 3.1415926535898 * 36.0


class DobotException(Exception):
    pass


class Position(NamedTuple):

    x: float
    y: float
    z: float
    r: float


class Joints(NamedTuple):

    j1: float
    j2: float
    j3: float
    j4: float

    def in_radians(self) -> "Joints":
        return Joints(math.radians(self.j1), math.radians(self.j2), math.radians(self.j3), math.radians(self.j4))


class Pose(NamedTuple):

    position: Position
    joints: Joints


class Alarm(IntEnum):

    COMMON_RESETTING = 0x00,
    COMMON_UNDEFINED_INSTRUCTION = 0x01,
    COMMON_FILE_SYSTEM = 0x02,
    COMMON_MCU_FPGA_COMM = 0x03,
    COMMON_ANGLE_SENSOR = 0x04

    PLAN_INV_SINGULARITY = 0x10,
    PLAN_INV_CALC = 0x11,
    PLAN_INV_LIMIT = 0x12, # !!!
    PLAN_PUSH_DATA_REPEAT = 0x13,
    PLAN_ARC_INPUT_PARAM = 0x14,
    PLAN_JUMP_PARAM = 0x15,
    PLAN_LINE_HAND = 0x16,
    PLAN_LINE_OUT_SPACE = 0x17,
    PLAN_ARC_OUT_SPACE = 0x18,
    PLAN_MOTIONTYPE = 0x19,
    PLAN_SPEED_INPUT_PARAM = 0x1A,
    PLAN_CP_CALC = 0x1B,

    MOVE_INV_SINGULARITY = 0x20,
    MOVE_INV_CALC = 0x21,
    MOVE_INV_LIMIT = 0x22,

    OVERSPEED_AXIS1 = 0x30,
    OVERSPEED_AXIS2 = 0x31,
    OVERSPEED_AXIS3 = 0x32,
    OVERSPEED_AXIS4 = 0x33,

    LIMIT_AXIS1_POS = 0x40,
    LIMIT_AXIS1_NEG = 0x41,
    LIMIT_AXIS2_POS = 0x42,
    LIMIT_AXIS2_NEG = 0x43,
    LIMIT_AXIS3_POS = 0x44,
    LIMIT_AXIS3_NEG = 0x45,
    LIMIT_AXIS4_POS = 0x46,
    LIMIT_AXIS4_NEG = 0x47,
    LIMIT_AXIS23_POS = 0x48,
    LIMIT_AXIS23_NEG = 0x49

    LOSE_STEP_AXIS1 = 0x50,
    LOSE_STEP_AXIS2 = 0x51
    LOSE_STEP_AXIS3 = 0x52
    LOSE_STEP_AXIS4 = 0x53

    OTHER_AXIS1_DRV_ALARM = 0x60,
    OTHER_AXIS1_OVERFLOW = 0x61,
    OTHER_AXIS1_FOLLOW = 0x62,
    OTHER_AXIS2_DRV_ALARM = 0x63,
    OTHER_AXIS2_OVERFLOW = 0x64,
    OTHER_AXIS2_FOLLOW = 0x65,
    OTHER_AXIS3_DRV_ALARM = 0x66,
    OTHER_AXIS3_OVERFLOW = 0x67,
    OTHER_AXIS3_FOLLOW = 0x68,
    OTHER_AXIS4_DRV_ALARM = 0x69,
    OTHER_AXIS4_OVERFLOW = 0x6A,
    OTHER_AXIS4_FOLLOW = 0x6B,

    MOTOR_REAR_ENCODER = 0x70,
    MOTOR_REAR_TEMPERATURE_HIGH = 0x71
    MOTOR_REAR_TEMPERATURE_LOW = 0x72,
    MOTOR_REAR_LOCK_CURRENT = 0x73,
    MOTOR_REAR_BUSV_HIGH = 0x74,
    MOTOR_REAR_BUSV_LOW = 0x75,
    MOTOR_REAR_OVERHEAT = 0x76,
    MOTOR_REAR_RUNAWAY = 0x77,
    MOTOR_REAR_BATTERY_LOW = 0x78,
    MOTOR_REAR_PHASE_SHORT = 0x79,
    MOTOR_REAR_PHASE_WRONG = 0x7A,
    MOTOR_REAR_LOST_SPEED = 0x7B,
    MOTOR_REAR_NOT_STANDARDIZE = 0x7C,
    ENCODER_REAR_NOT_STANDARDIZE = 0x7D,
    MOTOR_REAR_CAN_BROKE = 0x7E,

    MOTOR_FRONT_ENCODER = 0x80,
    MOTOR_FRONT_TEMPERATURE_HIGH = 0x81,
    MOTOR_FRONT_TEMPERATURE_LOW = 0x82,
    MOTOR_FRONT_LOCK_CURRENT = 0x83,
    MOTOR_FRONT_BUSV_HIGH = 0x84,
    MOTOR_FRONT_BUSV_LOW = 0x85,
    MOTOR_FRONT_OVERHEAT = 0x86,
    MOTOR_FRONT_RUNAWAY = 0x87,
    MOTOR_FRONT_BATTERY_LOW = 0x88,
    MOTOR_FRONT_PHASE_SHORT = 0x89,
    MOTOR_FRONT_PHASE_WRONG = 0x8A,
    MOTOR_FRONT_LOST_SPEED = 0x8B,
    MOTOR_FRONT_NOT_STANDARDIZE = 0x8C,
    ENCODER_FRONT_NOT_STANDARDIZE = 0x8D,
    MOTOR_FRONT_CAN_BROKE = 0x8E,

    MOTOR_Z_ENCODER = 0x90,
    MOTOR_Z_TEMPERATURE_HIGH = 0x91,
    MOTOR_Z_TEMPERATURE_LOW = 0x92,
    MOTOR_Z_LOCK_CURRENT = 0x93,
    MOTOR_Z_BUSV_HIGH = 0x94,
    MOTOR_Z_BUSV_LOW = 0x95,
    MOTOR_Z_OVERHEAT = 0x96,
    MOTOR_Z_RUNAWAY = 0x97,
    MOTOR_Z_BATTERY_LOW = 0x98,
    MOTOR_Z_PHASE_SHORT = 0x99,
    MOTOR_Z_PHASE_WRONG = 0x9A,
    MOTOR_Z_LOST_SPEED = 0x9B,
    MOTOR_Z_NOT_STANDARDIZE = 0x9C,
    ENCODER_Z_NOT_STANDARDIZE = 0x9D,
    MOTOR_Z_CAN_BROKE = 0x9E,

    MOTOR_R_ENCODER = 0xA0,
    MOTOR_R_TEMPERATURE_HIGH = 0xA1,
    MOTOR_R_TEMPERATURE_LOW = 0xA2,
    MOTOR_R_LOCK_CURRENT = 0xA3,
    MOTOR_R_BUSV_HIGH = 0xA4,
    MOTOR_R_BUSV_LOW = 0xA5,
    MOTOR_R_OVERHEAT = 0xA6,
    MOTOR_R_RUNAWAY = 0xA7,
    MOTOR_R_BATTERY_LOW = 0xA8,
    MOTOR_R_PHASE_SHORT = 0xA9
    MOTOR_R_PHASE_WRONG = 0xAA,
    MOTOR_R_LOST_SPEED = 0xAB,
    MOTOR_R_NOT_STANDARDIZE = 0xAC,
    ENCODER_R_NOT_STANDARDIZE = 0xAD,
    MOTOR_R_CAN_BROKE = 0xAE,

    MOTOR_ENDIO_IO = 0xB0,
    MOTOR_ENDIO_RS485_WRONG = 0xB1,
    MOTOR_ENDIO_CAN_BROKE = 0xB2


class Dobot:

    def __init__(self, port: Optional[str] = None) -> None:

        self.logger = logging.Logger(__name__)
        self._lock = RLock()

        if port is None:
            # Find the serial port
            ports = list_ports.comports()
            for thing in ports:
                if thing.vid in (4292, 6790):
                    self.logger.debug(f"Found a com port to talk to DOBOT ({thing}).")
                    port = thing.device
                    break
            else:
                raise DobotException("Device not found!")

        try:
            self._ser = serial.Serial(
                port,
                baudrate=115200,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS)
        except serial.serialutil.SerialException as e:
            raise DobotException from e

        self.logger.debug('pydobot: %s open' % self._ser.name if self._ser.isOpen() else 'failed to open serial port')

        self._set_queued_cmd_start_exec()
        self._set_queued_cmd_clear()
        self._set_ptp_joint_params(200, 200, 200, 200, 200, 200, 200, 200)
        self._set_ptp_coordinate_params(velocity=200, acceleration=200)
        self._set_ptp_jump_params(10, 200)
        self._set_ptp_common_params(velocity=100, acceleration=100)

        alarms = self.get_alarms()

        if alarms:
            self.logger.warning(f"Clearing alarms: {', '.join(map(str, alarms))}.")
            self.clear_alarms()

    def close(self) -> None:
        with self._lock:
            self._ser.close()
        self.logger.debug('pydobot: %s closed' % self._ser.name)

    def _send_command(self, msg, wait = False) -> Message:
        with self._lock:
            self._ser.reset_input_buffer()
            self._send_message(msg)
            msg = self._read_message()
        if msg is None:
            raise DobotException("No response!")
        if not wait:
            return msg
        
        expected_idx = struct.unpack_from('L', msg.params, 0)[0]
        while True:
            current_idx = self._get_queued_cmd_current_index()

            if current_idx != expected_idx:
                time.sleep(0.1)
                continue
            break
        return msg
        
        

    def _send_message(self, msg) -> None:

        self.logger.debug('pydobot: >>', msg)
        with self._lock:
            self._ser.write(msg.bytes())

    def _read_message(self) -> Optional[Message]:

        # Search for begin
        begin_found = False
        last_byte = None
        tries = 5
        while not begin_found and tries > 0:
            current_byte = ord(self._ser.read(1))
            if current_byte == 170:
                if last_byte == 170:
                    begin_found = True
            last_byte = current_byte
            tries = tries - 1
        if begin_found:
            payload_length = ord(self._ser.read(1))
            payload_checksum = self._ser.read(payload_length + 1)
            if len(payload_checksum) == payload_length + 1:
                b = bytearray([0xAA, 0xAA])
                b.extend(bytearray([payload_length]))
                b.extend(payload_checksum)
                msg = Message(b)
                self.logger.debug('Lenght', payload_length)
                self.logger.debug(payload_checksum)
                self.logger.debug('MessageID:', payload_checksum[0])
                self.logger.debug('pydobot: <<', ":".join('{:02x}'.format(x) for x in b))
                return msg
        return None

    def get_pose(self) -> Pose:
        msg = Message()
        msg.id = 10
        response = self._send_command(msg)

        return Pose(
            Position(
                struct.unpack_from('f', response.params, 0)[0],
                struct.unpack_from('f', response.params, 4)[0],
                struct.unpack_from('f', response.params, 8)[0],
                struct.unpack_from('f', response.params, 12)[0]
            ),
            Joints(
                struct.unpack_from('f', response.params, 16)[0],
                struct.unpack_from('f', response.params, 20)[0],
                struct.unpack_from('f', response.params, 24)[0],
                struct.unpack_from('f', response.params, 28)[0]
            )
        )

    def get_alarms(self) -> Set[Alarm]:

        msg = Message()
        msg.id = 20
        response = self._send_command(msg)  # 32 bytes

        ret: Set[Alarm] = set()

        for idx in range(16):
            alarm_byte = struct.unpack_from('B', response.params, idx)[0]
            for alarm_index in [i for i in range(alarm_byte.bit_length()) if alarm_byte & (1 << i)]:
                ret.add(Alarm(idx*8+alarm_index))
        return ret

    def clear_alarms(self) -> None:

        msg = Message()
        msg.id = 20
        msg.ctrl = 0x01
        self._send_command(msg)  # empty response

    def _set_cp_cmd(self, x, y, z):
        msg = Message()
        msg.id = 91
        msg.ctrl = 0x03
        msg.params = bytearray(bytes([0x01]))
        msg.params.extend(bytearray(struct.pack('f', x)))
        msg.params.extend(bytearray(struct.pack('f', y)))
        msg.params.extend(bytearray(struct.pack('f', z)))
        msg.params.append(0x00)
        return self._send_command(msg)

    def _set_ptp_joint_params(self, v_x, v_y, v_z, v_r, a_x, a_y, a_z, a_r):
        msg = Message()
        msg.id = 80
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray(struct.pack('f', v_x)))
        msg.params.extend(bytearray(struct.pack('f', v_y)))
        msg.params.extend(bytearray(struct.pack('f', v_z)))
        msg.params.extend(bytearray(struct.pack('f', v_r)))
        msg.params.extend(bytearray(struct.pack('f', a_x)))
        msg.params.extend(bytearray(struct.pack('f', a_y)))
        msg.params.extend(bytearray(struct.pack('f', a_z)))
        msg.params.extend(bytearray(struct.pack('f', a_r)))
        return self._send_command(msg)

    def _set_ptp_coordinate_params(self, velocity, acceleration):
        msg = Message()
        msg.id = 81
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray(struct.pack('f', velocity)))
        msg.params.extend(bytearray(struct.pack('f', velocity)))
        msg.params.extend(bytearray(struct.pack('f', acceleration)))
        msg.params.extend(bytearray(struct.pack('f', acceleration)))
        return self._send_command(msg)

    def _set_ptp_jump_params(self, jump, limit):
        msg = Message()
        msg.id = 82
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray(struct.pack('f', jump)))
        msg.params.extend(bytearray(struct.pack('f', limit)))
        return self._send_command(msg)

    def _set_ptp_common_params(self, velocity, acceleration):
        msg = Message()
        msg.id = 83
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray(struct.pack('f', velocity)))
        msg.params.extend(bytearray(struct.pack('f', acceleration)))
        return self._send_command(msg)

    def _set_ptp_cmd(self, x, y, z, r, mode, wait):
        msg = Message()
        msg.id = 84
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray([mode]))
        msg.params.extend(bytearray(struct.pack('f', x)))
        msg.params.extend(bytearray(struct.pack('f', y)))
        msg.params.extend(bytearray(struct.pack('f', z)))
        msg.params.extend(bytearray(struct.pack('f', r)))
        return self._send_command(msg, wait)

    def _set_end_effector_suction_cup(self, enable=False):
        msg = Message()
        msg.id = 62
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray([0x01]))
        if enable is True:
            msg.params.extend(bytearray([0x01]))
        else:
            msg.params.extend(bytearray([0x00]))
        return self._send_command(msg)

    def _set_end_effector_gripper(self, enable=False):
        msg = Message()
        msg.id = 63
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray([0x01]))
        if enable is True:
            msg.params.extend(bytearray([0x01]))
        else:
            msg.params.extend(bytearray([0x00]))
        return self._send_command(msg)

    def _set_end_effector_laser(self, power=255, enable=False):
        """Enables the laser. Power from 0 to 255. """
        msg = Message()
        msg.id = 61
        msg.ctrl = 0x03
        msg.params = bytearray([])
        # msg.params.extend(bytearray([0x01]))
        if enable is True:
            msg.params.extend(bytearray([0x01]))
        else:
            msg.params.extend(bytearray([0x00]))
        # Assuming the last byte is power. Seems to have little effect
        msg.params.extend(bytearray([power]))
        return self._send_command(msg)

    def _set_queued_cmd_start_exec(self):
        msg = Message()
        msg.id = 240
        msg.ctrl = 0x01
        return self._send_command(msg)

    def _set_queued_cmd_stop_exec(self):
        msg = Message()
        msg.id = 241
        msg.ctrl = 0x01
        return self._send_command(msg)

    def _set_queued_cmd_clear(self):
        msg = Message()
        msg.id = 245
        msg.ctrl = 0x01
        return self._send_command(msg)

    def _get_queued_cmd_current_index(self):
        msg = Message()
        msg.id = 246
        response = self._send_command(msg)
        if response and response.id == 246:
            return self._extract_cmd_index(response)
        else:
            return -1

    @staticmethod
    def _extract_cmd_index(response):
        return struct.unpack_from('I', response.params, 0)[0]

    def wait_for_cmd(self, cmd_id):
        current_cmd_id = self._get_queued_cmd_current_index()
        while cmd_id > current_cmd_id:
            self.logger.debug("Current-ID", current_cmd_id)
            self.logger.debug("Waiting for", cmd_id)

            current_cmd_id = self._get_queued_cmd_current_index()

    def _set_home_cmd(self):
        msg = Message()
        msg.id = 31
        msg.ctrl = 0x03
        msg.params = bytearray([])
        return self._send_command(msg)

    def _set_arc_cmd(self, x, y, z, r, cir_x, cir_y, cir_z, cir_r):
        msg = Message()
        msg.id = 101
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray(struct.pack('f', cir_x)))
        msg.params.extend(bytearray(struct.pack('f', cir_y)))
        msg.params.extend(bytearray(struct.pack('f', cir_z)))
        msg.params.extend(bytearray(struct.pack('f', cir_r)))
        msg.params.extend(bytearray(struct.pack('f', x)))
        msg.params.extend(bytearray(struct.pack('f', y)))
        msg.params.extend(bytearray(struct.pack('f', z)))
        msg.params.extend(bytearray(struct.pack('f', r)))
        return self._send_command(msg)
    
    def _set_version_sliding_rail_cmd(self, version,):
        msg = Message()
        msg.id = 3
        msg.ctrl = 0x02
        msg.params = bytearray([])
        msg.params.extend(bytearray(struct.pack('f', version)))
        return self._send_command(msg, wait=False)

    def _set_home_coordinate(self, x, y, z, r):
        msg = Message()
        msg.id = 30
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray(struct.pack('f', x)))
        msg.params.extend(bytearray(struct.pack('f', y)))
        msg.params.extend(bytearray(struct.pack('f', z)))
        msg.params.extend(bytearray(struct.pack('f', r)))
        return self._send_command(msg)

    def _set_jog_coordinate_params(self, vx, vy, vz, vr, ax=100, ay=100, az=100, ar=100):
        msg = Message()
        msg.id = 71
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray(struct.pack('f', vx)))
        msg.params.extend(bytearray(struct.pack('f', vy)))
        msg.params.extend(bytearray(struct.pack('f', vz)))
        msg.params.extend(bytearray(struct.pack('f', vr)))
        msg.params.extend(bytearray(struct.pack('f', ax)))
        msg.params.extend(bytearray(struct.pack('f', ay)))
        msg.params.extend(bytearray(struct.pack('f', az)))
        msg.params.extend(bytearray(struct.pack('f', ar)))
        return self._send_command(msg)

    def _set_jog_command(self, cmd):
        msg = Message()
        msg.id = 73
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray([0x0]))
        msg.params.extend(bytearray([cmd]))
        return self._send_command(msg)

    def jog_x(self, v):

        self._set_jog_coordinate_params(abs(v), 0, 0, 0,)
        if v > 0:
            cmd = 1
        elif v < 0:
            cmd = 2
        else:
            cmd = 0

        self.wait_for_cmd(self._extract_cmd_index(self._set_jog_command(cmd)))

    def jog_y(self, v):

        self._set_jog_coordinate_params(0, abs(v), 0, 0)
        if v > 0:
            cmd = 3
        elif v < 0:
            cmd = 4
        else:
            cmd = 0

        self.wait_for_cmd(self._extract_cmd_index(self._set_jog_command(cmd)))

    def jog_z(self, v):

        self._set_jog_coordinate_params(0, 0, abs(v), 0)
        if v > 0:
            cmd = 5
        elif v < 0:
            cmd = 6
        else:
            cmd = 0

        self.wait_for_cmd(self._extract_cmd_index(self._set_jog_command(cmd)))

    def jog_r(self, v):

        self._set_jog_coordinate_params(0, 0, 0, abs(v))
        if v > 0:
            cmd = 7
        elif v < 0:
            cmd = 8
        else:
            cmd = 0

        self.wait_for_cmd(self._extract_cmd_index(self._set_jog_command(cmd)))

    def set_io(self, address: int, state: bool):

        if not 1 <= address <= 22:
            raise DobotException("Invalid address range.")

        msg = Message()
        msg.id = 131
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray(struct.pack('B', address)))
        msg.params.extend(bytearray(struct.pack('B', int(state))))

        self.wait_for_cmd(self._extract_cmd_index(self._send_command(msg)))

    def set_hht_trig_output(self, state: bool) -> None:

        msg = Message()
        msg.id = 41
        msg.ctrl = 0x02
        msg.params = bytearray([])
        msg.params.extend(bytearray(struct.pack('B', int(state))))

        self._send_command(msg)

    def get_hht_trig_output(self) -> bool:

        msg = Message()
        msg.id = 41
        msg.ctrl = 0

        response = self._send_command(msg)
        return bool(struct.unpack_from('B', response.params, 0)[0])


    def go_arc(self, x, y, z, r, cir_x, cir_y, cir_z, cir_r):
        return self._extract_cmd_index(self._set_arc_cmd(x, y, z, r, cir_x, cir_y, cir_z, cir_r))

    def suck(self, enable):
        return self._extract_cmd_index(self._set_end_effector_suction_cup(enable))

    def set_home(self, x, y, z, r=0.):
        self._set_home_coordinate(x, y, z, r)

    def home(self):
        return self._extract_cmd_index(self._set_home_cmd())

    def grip(self, enable):
        return self._extract_cmd_index(self._set_end_effector_gripper(enable))

    def laze(self, power=0, enable=False):
        return self._extract_cmd_index(self._set_end_effector_laser(power, enable))

    def speed(self, velocity=100., acceleration=100.):
        self.wait_for_cmd(self._extract_cmd_index(self._set_ptp_common_params(velocity, acceleration)))
        self.wait_for_cmd(self._extract_cmd_index(self._set_ptp_coordinate_params(velocity, acceleration)))

    def conveyor_belt(self, speed, direction=1, interface=0):
        if 0.0 <= speed <= 1.0 and (direction == 1 or direction == -1):
            motor_speed = int(50 * speed * STEP_PER_CIRCLE / MM_PER_CIRCLE * direction)
            self._set_stepper_motor(motor_speed, interface)
        else:
            raise DobotException("Wrong Parameter")

    def _set_stepper_motor(self, speed, interface=0, motor_control=True):
        msg = Message()
        msg.id = 0x87
        msg.ctrl = 0x03
        msg.params = bytearray([])
        if interface == 1:
            msg.params.extend(bytearray([0x01]))
        else:
            msg.params.extend(bytearray([0x00]))
        if motor_control is True:
            msg.params.extend(bytearray([0x01]))
        else:
            msg.params.extend(bytearray([0x00]))
        msg.params.extend(bytearray(struct.pack('i', speed)))
        return self._send_command(msg)

    def _set_stepper_motor_distance(self, speed, distance, interface=0, motor_control=True):
        msg = Message()
        msg.id = 0x88
        msg.ctrl = 0x03
        msg.params = bytearray([])
        if interface == 1:
            msg.params.extend(bytearray([0x01]))
        else:
            msg.params.extend(bytearray([0x00]))
        if motor_control is True:
            msg.params.extend(bytearray([0x01]))
        else:
            msg.params.extend(bytearray([0x00]))
        msg.params.extend(bytearray(struct.pack('i', speed)))
        msg.params.extend(bytearray(struct.pack('I', distance)))
        return self._send_command(msg)

    def _set_cp_params(self, velocity, acceleration, period):

        msg = Message()
        msg.id = 90
        msg.ctrl = 0x3
        msg.params = bytearray([])
        msg.params.extend(bytearray(struct.pack('f', acceleration)))
        msg.params.extend(bytearray(struct.pack('f', velocity)))
        msg.params.extend(bytearray(struct.pack('f', period)))
        msg.params.extend(bytearray([0x0]))  # non real-time mode (what does it mean??)
        return self._send_command(msg)

    def _set_cple_cmd(self, x, y, z, power, absolute=False):

        assert 0 <= power <= 100

        msg = Message()
        msg.id = 92
        msg.ctrl = 0x3
        msg.params = bytearray([int(absolute)])
        msg.params.extend(bytearray(struct.pack('f', x)))
        msg.params.extend(bytearray(struct.pack('f', y)))
        msg.params.extend(bytearray(struct.pack('f', z)))
        msg.params.extend(bytearray(struct.pack('f', power)))
        return self._send_command(msg)

    def engrave(self, image, pixel_size, low=0.0, high=40.0, velocity=5, acceleration=5, actual_acceleration=5):
        image = image.astype("float64")
        image = 255.0 - image
        image = (image - image.min()) / (image.max() - image.min()) * (high - low) + low

        x, y, z = self.get_pose().position[0:3]  # get current/starting position

        self.wait_for_cmd(self.laze(0, False))
        self._set_queued_cmd_clear()
        self.wait_for_cmd(self._extract_cmd_index(self._set_cp_params(velocity, acceleration, actual_acceleration)))

        self._set_queued_cmd_stop_exec()
        stopped = True

        indexes = deque()

        for row_idx, row in enumerate(image):

            # first feed the queue to be almost full
            if stopped and len(indexes) > MAX_QUEUE_LEN-2:
                self._set_queued_cmd_start_exec()
                stopped = False

            if row_idx % 2 == 1:
                data = reversed(row)
                rev = True
            else:
                data = row
                rev = False

            for col_idx, ld in enumerate(data):

                if not rev:
                    y_ofs = col_idx * pixel_size
                else:
                    y_ofs = (len(row)-1 - col_idx) * pixel_size

                indexes.append(
                    self._extract_cmd_index(self._set_cple_cmd(x + row_idx * pixel_size, y + y_ofs, z, ld, True)))

                # then feed it as necessary to keep it almost full
                while not stopped and len(indexes) > MAX_QUEUE_LEN-12:
                    self.wait_for_cmd(indexes.popleft())

        self.wait_for_cmd(self.laze(0, False))
        
    
    PORT_GP1 = 0x00
    PORT_GP2 = 0x01
    PORT_GP4 = 0x02
    PORT_GP5 = 0x03

    def conveyor_belt_distance(self, speed_mm_per_sec, distance_mm, direction=1, interface=0):
        if speed_mm_per_sec > 100:
            raise DobotException("Speed must be less than 100mm/s")


        MM_PER_REV = 34 * math.pi  # Seems to actually be closer to 36mm when measured but 34 works better
        STEP_ANGLE_DEG = 1.8
        STEPS_PER_REV = 360.0 / STEP_ANGLE_DEG * 10.0 * 16.0 / 2.0  # Spec sheet says that it can do 1.8deg increments, no idea what the 10 * 16 / 2 fuck factor is....
        distance_steps = distance_mm / MM_PER_REV * STEPS_PER_REV
        speed_steps_per_sec = speed_mm_per_sec / MM_PER_REV * STEPS_PER_REV * direction
        return self._extract_cmd_index(self._set_stepper_motor_distance(int(speed_steps_per_sec), int(distance_steps), interface))



    def set_color(self, enable=True, port=PORT_GP2, version=0x1):
        msg = Message()
        msg.id = 137
        msg.ctrl = 0x03
        msg.params = bytearray([])
        msg.params.extend(bytearray([int(enable)]))
        msg.params.extend(bytearray([port]))
        msg.params.extend(bytearray([version]))  # Version1=0, Version2=1
        return self._extract_cmd_index(self._send_command(msg))

    def get_color(self, port=PORT_GP2, version=0x1):
        msg = Message()
        msg.id = 137
        msg.ctrl = 0x00
        msg.params = bytearray([])
        msg.params.extend(bytearray([port]))
        msg.params.extend(bytearray([0x01]))
        msg.params.extend(bytearray([version]))  # Version1=0, Version2=1
        response = self._send_command(msg)
        print(response)
        r = struct.unpack_from('?', response.params, 0)[0]
        g = struct.unpack_from('?', response.params, 1)[0]
        b = struct.unpack_from('?', response.params, 2)[0]
        return [r, g, b]
    
    def set_ir(self, enable=True, port=PORT_GP4):
        msg = Message()
        msg.id = 138
        msg.ctrl = 0x02
        msg.params = bytearray([])
        msg.params.extend(bytearray([int(enable)]))
        msg.params.extend(bytearray([port]))
        return self._extract_cmd_index(self._send_command(msg))

    def get_ir(self, port=PORT_GP4):
        msg = Message()
        msg.id = 138
        msg.ctrl = 0x00
        msg.params = bytearray([])
        msg.params.extend(bytearray([port]))
        response = self._send_command(msg)
        state = struct.unpack_from('?', response.params, 0)[0]
        return state
    
    def move_rel(self, x=0, y=0, z=0, r=0, wait = True):
        (xInit, yInit, zInit, rInit) = self.get_pose().position
        self.move_to(xInit+x, yInit+y, zInit+z, rInit+r, wait)
        
    
    def move_to(self, x=None, y=None, z=None, r=0, wait = True, mode=None, position=None):
        if position is not None:
            x, y, z, r = position.x, position.y, position.z, position.r
        elif x is None and y is None and z is None:
            raise ValueError("Either a Position object or x, y, z coordinates must be provided")
        
        current_pose = self.get_pose().position
        if x is None: x = current_pose.x
        if y is None: y = current_pose.y
        if z is None: z = current_pose.z
        if r is None: r = current_pose.r
        print(current_pose)
        
        if mode is None:
            mode = MODE_PTP.MOVJ_XYZ  # Use default mode if not provided
            
        return self._extract_cmd_index(self._set_ptp_cmd(x, y, z, r, mode, wait = wait))

    def _get_sliding_rail_status(self):
        """Get sliding rail enable status (WithL). Returns True if enabled, False otherwise."""
        msg = Message()
        msg.id = 3
        msg.ctrl = 0x00
        msg.params = bytearray([])
        response = self._send_command(msg)
        if response and len(response.params) > 0:
            return bool(response.params[0])
        raise DobotException("No response or invalid response for sliding rail status.")

    def _set_sliding_rail_status(self, enabled: bool, version: int = 0):
        """Set sliding rail enable status (WithL). enabled=True/False, version=0 (VER_V1) or 1 (VER_V2)."""
        msg = Message()
        msg.id = 3
        msg.ctrl = 0x01  # Set command
        msg.params = bytearray([])
        # WithL struct: uint8_t isWithL, Version version
        msg.params.extend(bytearray([1 if enabled else 0]))
        msg.params.extend(bytearray([version]))
        response = self._send_command(msg, wait=False)
        return response

    def _set_ptp_with_l_cmd(self, ptp_mode: int, x: float, y: float, z: float, r: float, l: float, is_queued: int = 1, wait: bool = True):
        """
        Execute PTP command with the sliding rail (SetPTPWithLCmd).
        ptp_mode: int (0-9)
        x, y, z, r: float (coordinates or increments)
        l: float (distance that sliding rail moves)
        is_queued: 1 (queued) or 0 (not queued)
        wait: whether to wait for command completion
        """
        msg = Message()
        msg.id = 86
        msg.ctrl = 0x03  # Set command
        msg.isQueued = is_queued
        msg.params = bytearray([])
        msg.params.extend(bytearray([ptp_mode]))
        msg.params.extend(bytearray(struct.pack('f', x)))
        msg.params.extend(bytearray(struct.pack('f', y)))
        msg.params.extend(bytearray(struct.pack('f', z)))
        msg.params.extend(bytearray(struct.pack('f', r)))
        msg.params.extend(bytearray(struct.pack('f', l)))
        msg.refresh()
        response = self._send_command(msg, wait=wait)
        return response

    def ptp_with_l(self, ptp_mode: int, x: float, y: float, z: float, r: float, l: float, is_queued: int = 1, wait: bool = True):
        """
        Public method to execute PTP with sliding rail. Returns queuedCmdIndex if available.
        """
        response = self._set_ptp_with_l_cmd(ptp_mode, x, y, z, r, l, is_queued, wait)
        # Response may contain queuedCmdIndex (uint64) or be empty
        if response and response.params and len(response.params) >= 8:
            return struct.unpack_from('Q', response.params, 0)[0]
        return None
