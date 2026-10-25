"""
Smart Home Sensor, Actuator, and Appliance Nodes for ROS 2.
Implements:
- [#1] Smart Appliance (Washer)
- [#2] Energy Monitoring & Peak Shaving
- [#4] Personal Health Monitoring
- [#5] Multi-sensor pairs for indirect measurements (Fire, Leak, Occupancy)
- [#6, #21] Climate Control / HVAC Actuator
- [#7, #18] Smart Lighting & Emergency Strobe Actuator
- [#12, #13, #17] Video Camera & Vision Analytics Actuator
- [#19] Motorized Water Shutoff Valve Actuator
- [#20] Electromagnetic Emergency Exit Door Lock Actuator
"""

import time
import json
import math
import random
from typing import Dict, Any, List

from .ros_compat import LifecycleNode, QoSProfile
from .interfaces import (
    SensorTelemetryMsg, DeviceStatusMsg, EnergyStatusMsg, HealthVitalsMsg,
    VisionDetectionMsg, PollSensorRequest, PollSensorResponse,
    ActuatorCommandRequest, ActuatorCommandResponse
)
from .security import SecurityManager

class SmartWasherNode(LifecycleNode):
    """[#1] Smart Washing Machine Appliance."""
    def __init__(self, node_name: str = "appliance_washer"):
        super().__init__(node_name)
        self.device_id = "appliance_washer_01"
        self.device_type = "APPLIANCE"
        self.status = "RUNNING_SPIN_CYCLE"
        self.power_draw_w = 1850.0
        self.vibration_g = 0.42
        self.drum_rpm = 1200
        self.cycle_time_remaining = 35

        # ROS Service for Polling (Continuous polling pattern)
        self.create_service(PollSensorResponse, f"/device/{self.device_id}/poll", self.handle_poll)
        # Actuator command service
        self.create_service(ActuatorCommandResponse, f"/actuators/{self.device_id}/command", self.handle_command)

    def handle_poll(self, req: PollSensorRequest) -> PollSensorResponse:
        return PollSensorResponse(
            success=True,
            device_id=self.device_id,
            values=[self.power_draw_w, self.vibration_g, float(self.drum_rpm), float(self.cycle_time_remaining)],
            value_keys=["power_w", "vibration_g", "rpm", "remaining_min"],
            status_message=f"State: {self.status}"
        )

    def handle_command(self, req: ActuatorCommandRequest) -> ActuatorCommandResponse:
        cmd = req.command.upper()
        if cmd in ["STOP", "PAUSE", "OFF"]:
            self.status = "EMERGENCY_STOPPED"
            self.power_draw_w = 12.0
            self.drum_rpm = 0
            self.get_logger().warn(f"[{self.device_id}] Emergency STOP executed to prevent water damage / fire.")
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state=self.status, message="Washer paused.")
        elif cmd in ["START", "RESUME"]:
            self.status = "RUNNING_SPIN_CYCLE"
            self.power_draw_w = 1850.0
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state=self.status, message="Washer resumed.")
        return ActuatorCommandResponse(success=False, actuator_id=self.device_id, current_state=self.status, message="Unknown command.")


class EnergyManagerNode(LifecycleNode):
    """[#2] Smart Grid AMS Meter, Battery Management & Peak Shaving."""
    def __init__(self, node_name: str = "energy_manager"):
        super().__init__(node_name)
        self.device_id = "ams_energy_meter_01"
        self.total_power_kw = 4.2
        self.voltage_v = 230.4
        self.frequency_hz = 50.02
        self.power_limit_kw = 9.0
        self.battery_storage_pct = 94.5
        self.peak_shaving_active = False

        self.energy_pub = self.create_publisher(EnergyStatusMsg, "/energy/status", QoSProfile(depth=10))
        self.create_service(PollSensorResponse, f"/device/{self.device_id}/poll", self.handle_poll)
        self.create_timer(1.0, self.publish_energy_status)

    def publish_energy_status(self):
        msg = EnergyStatusMsg(
            total_grid_power_kw=self.total_power_kw,
            grid_voltage_v=self.voltage_v,
            grid_frequency_hz=self.frequency_hz,
            power_budget_limit_kw=self.power_limit_kw,
            peak_shaving_active=self.peak_shaving_active,
            throttled_appliances=["ev_charger"] if self.peak_shaving_active else [],
            battery_storage_pct=self.battery_storage_pct
        )
        self.energy_pub.publish(msg)

    def handle_poll(self, req: PollSensorRequest) -> PollSensorResponse:
        return PollSensorResponse(
            success=True,
            device_id=self.device_id,
            values=[self.total_power_kw, self.voltage_v, self.frequency_hz, self.battery_storage_pct],
            value_keys=["power_kw", "voltage_v", "freq_hz", "battery_pct"],
            status_message="Grid stable"
        )


class HealthMonitorNode(LifecycleNode):
    """[#4] Personal Health Monitoring Wearable (Pulse, SpO2, Fall Accel)."""
    def __init__(self, node_name: str = "health_monitor"):
        super().__init__(node_name)
        self.device_id = "health_wearable_01"
        self.occupant_id = "resident_elderly_01"
        self.heart_rate = 74.0
        self.spo2 = 98.2
        self.skin_temp = 36.7
        self.fall_detected = False
        self.impact_g = 1.0
        self.activity_state = "RESTING"

        self.vitals_pub = self.create_publisher(HealthVitalsMsg, "/health/vitals", QoSProfile(depth=10))
        self.create_service(PollSensorResponse, f"/device/{self.device_id}/poll", self.handle_poll)

    def simulate_fall(self, impact_force_g: float = 4.8):
        self.fall_detected = True
        self.impact_g = impact_force_g
        self.activity_state = "FALL_SUSPECTED"
        self.heart_rate = 118.0
        self.get_logger().error(f"FALL DETECTED for occupant {self.occupant_id}! Impact: {impact_force_g}g")
        self._publish_vitals()

    def _publish_vitals(self):
        msg = HealthVitalsMsg(
            occupant_id=self.occupant_id,
            heart_rate_bpm=self.heart_rate,
            blood_oxygen_spo2=self.spo2,
            skin_temperature_c=self.skin_temp,
            fall_detected=self.fall_detected,
            impact_force_g=self.impact_g,
            activity_state=self.activity_state
        )
        self.vitals_pub.publish(msg)

    def handle_poll(self, req: PollSensorRequest) -> PollSensorResponse:
        return PollSensorResponse(
            success=True,
            device_id=self.device_id,
            values=[self.heart_rate, self.spo2, self.skin_temp, 1.0 if self.fall_detected else 0.0, self.impact_g],
            value_keys=["heart_rate_bpm", "spo2_pct", "skin_temp_c", "fall_flag", "impact_g"],
            status_message=f"Activity: {self.activity_state}"
        )


class FireSensorsNode(LifecycleNode):
    """
    [#5] Dual Sensor Pair for Fire Verification:
    - Sensor 1: Fast-response thermal sensor (Temperature Rate-of-Rise dT/dt)
    - Sensor 2: Optical ionization smoke particle chamber / CO sensor (dC/dt)
    """
    def __init__(self, node_name: str = "fire_sensors"):
        super().__init__(node_name)
        self.device_id = "fire_sensor_combo_01"
        self.location = "living_room"
        self.temp_c = 21.5
        self.smoke_obscuration_pct_m = 0.02
        self.co_ppm = 1.5

        self.create_service(PollSensorResponse, f"/device/{self.device_id}/poll", self.handle_poll)

    def inject_fire(self, temp: float = 68.5, smoke: float = 8.4, co: float = 55.0):
        self.temp_c = temp
        self.smoke_obscuration_pct_m = smoke
        self.co_ppm = co
        self.get_logger().warn(f"Fire condition injected: Temp={temp}C, Smoke={smoke}%/m, CO={co}ppm")

    def handle_poll(self, req: PollSensorRequest) -> PollSensorResponse:
        return PollSensorResponse(
            success=True,
            device_id=self.device_id,
            values=[self.temp_c, self.smoke_obscuration_pct_m, self.co_ppm],
            value_keys=["temperature_c", "smoke_obscuration_pct_m", "co_ppm"],
            status_message=f"Location: {self.location}"
        )


class LeakSensorsNode(LifecycleNode):
    """
    [#5] Dual Sensor Pair for Water Leak Verification:
    - Sensor 1: Ultrasonic in-line pipe flow meter (Abnormal continuous liters/min)
    - Sensor 2: Floor conductive moisture resistivity grid (Ohms drop on puddle contact)
    """
    def __init__(self, node_name: str = "leak_sensors"):
        super().__init__(node_name)
        self.device_id = "leak_sensor_combo_01"
        self.location = "utility_room"
        self.flow_rate_l_min = 0.0
        self.floor_resistance_ohms = 100000.0  # Dry floor > 50k Ohm

        self.create_service(PollSensorResponse, f"/device/{self.device_id}/poll", self.handle_poll)

    def inject_leak(self, flow: float = 38.5, resistance: float = 120.0):
        self.flow_rate_l_min = flow
        self.floor_resistance_ohms = resistance
        self.get_logger().warn(f"Leak injected: Flow={flow} L/min, Floor Resistance={resistance} Ohm")

    def handle_poll(self, req: PollSensorRequest) -> PollSensorResponse:
        return PollSensorResponse(
            success=True,
            device_id=self.device_id,
            values=[self.flow_rate_l_min, self.floor_resistance_ohms],
            value_keys=["flow_rate_l_min", "floor_resistance_ohms"],
            status_message=f"Location: {self.location}"
        )


class OccupancySensorsNode(LifecycleNode):
    """
    [#5] Dual Sensor Pair for Room Occupancy:
    - Sensor 1: PIR Motion detector
    - Sensor 2: Ambient CO2 / Acoustic energy level
    """
    def __init__(self, node_name: str = "occupancy_sensors"):
        super().__init__(node_name)
        self.device_id = "occupancy_combo_01"
        self.location = "living_room"
        self.motion_detected = False
        self.co2_ppm = 410.0
        self.acoustic_db = 32.0

        self.create_service(PollSensorResponse, f"/device/{self.device_id}/poll", self.handle_poll)

    def set_occupied(self, motion: bool = True, co2: float = 850.0, db: float = 54.0):
        self.motion_detected = motion
        self.co2_ppm = co2
        self.acoustic_db = db

    def handle_poll(self, req: PollSensorRequest) -> PollSensorResponse:
        return PollSensorResponse(
            success=True,
            device_id=self.device_id,
            values=[1.0 if self.motion_detected else 0.0, self.co2_ppm, self.acoustic_db],
            value_keys=["motion_flag", "co2_ppm", "acoustic_db"],
            status_message=f"Location: {self.location}"
        )


class ClimateHvacNode(LifecycleNode):
    """[#6, #21] Climate Control / HVAC Actuator."""
    def __init__(self, node_name: str = "climate_hvac"):
        super().__init__(node_name)
        self.device_id = "hvac_controller_01"
        self.mode = "COMFORT"  # COMFORT, ECO, FIRE_LOCKOUT
        self.target_temp_c = 21.5
        self.fan_speed_pct = 40
        self.fresh_air_damper_open = True

        self.create_service(ActuatorCommandResponse, f"/actuators/{self.device_id}/command", self.handle_command)

    def handle_command(self, req: ActuatorCommandRequest) -> ActuatorCommandResponse:
        cmd = req.command.upper()
        if cmd == "FIRE_LOCKOUT":
            self.mode = "FIRE_LOCKOUT"
            self.fan_speed_pct = 0
            self.fresh_air_damper_open = False
            self.get_logger().error("HVAC in FIRE LOCKOUT: Fans stopped, fresh air dampers sealed.")
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state=self.mode, message="Damper closed, fan stopped.")
        elif cmd == "ECO":
            self.mode = "ECO"
            self.target_temp_c = 18.0
            self.fan_speed_pct = 20
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state=self.mode, message="HVAC set to ECO.")
        elif cmd == "COMFORT":
            self.mode = "COMFORT"
            self.target_temp_c = 21.5
            self.fan_speed_pct = 45
            self.fresh_air_damper_open = True
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state=self.mode, message="HVAC set to COMFORT.")
        return ActuatorCommandResponse(success=False, actuator_id=self.device_id, current_state=self.mode, message="Unknown HVAC mode.")


class LightingNode(LifecycleNode):
    """[#7, #18] Smart Lighting System & Emergency Strobe Actuator."""
    def __init__(self, node_name: str = "smart_lighting"):
        super().__init__(node_name)
        self.device_id = "lighting_controller_01"
        self.mode = "NORMAL"  # OFF, NORMAL, ECO_DIM, FULL_EVACUATION_100, STROBE_ALARM
        self.brightness_pct = 60

        self.create_service(ActuatorCommandResponse, f"/actuators/{self.device_id}/command", self.handle_command)

    def handle_command(self, req: ActuatorCommandRequest) -> ActuatorCommandResponse:
        cmd = req.command.upper()
        if cmd == "FULL_EVACUATION_100":
            self.mode = "FULL_EVACUATION_100"
            self.brightness_pct = 100
            self.get_logger().warn("Lighting: 100% full illumination activated along evacuation pathway.")
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state=self.mode, message="Evacuation lights 100%.")
        elif cmd == "STROBE_ALARM":
            self.mode = "STROBE_ALARM"
            self.brightness_pct = 100
            self.get_logger().warn("Lighting: Intruding alarm STROBE mode active.")
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state=self.mode, message="Intruder strobe active.")
        elif cmd == "ECO_DIM":
            self.mode = "ECO_DIM"
            self.brightness_pct = 20
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state=self.mode, message="Lights dimmed for eco.")
        elif cmd == "NORMAL":
            self.mode = "NORMAL"
            self.brightness_pct = 60
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state=self.mode, message="Lights set to normal.")
        return ActuatorCommandResponse(success=False, actuator_id=self.device_id, current_state=self.mode, message="Unknown light cmd.")


class WaterValveNode(LifecycleNode):
    """[#19] Motorized Main Water Shutoff Valve Actuator."""
    def __init__(self, node_name: str = "water_valve"):
        super().__init__(node_name)
        self.device_id = "main_water_valve_01"
        self.is_open = True

        self.create_service(ActuatorCommandResponse, f"/actuators/{self.device_id}/command", self.handle_command)

    def handle_command(self, req: ActuatorCommandRequest) -> ActuatorCommandResponse:
        cmd = req.command.upper()
        if cmd in ["CLOSE", "SHUTOFF"]:
            self.is_open = False
            self.get_logger().error(f"[{self.device_id}] EMERGENCY: Motorized water valve SHUT OFF within 280ms.")
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state="CLOSED", message="Water shutoff confirmed.")
        elif cmd in ["OPEN", "RESET"]:
            self.is_open = True
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state="OPEN", message="Water valve opened.")
        return ActuatorCommandResponse(success=False, actuator_id=self.device_id, current_state="OPEN" if self.is_open else "CLOSED", message="Unknown command.")


class EmergencyExitNode(LifecycleNode):
    """[#20] Fail-Safe Electromagnetic Emergency Door Lock Actuator."""
    def __init__(self, node_name: str = "emergency_exit"):
        super().__init__(node_name)
        self.device_id = "emergency_exit_lock_01"
        self.is_locked = True

        self.create_service(ActuatorCommandResponse, f"/actuators/{self.device_id}/command", self.handle_command)

    def handle_command(self, req: ActuatorCommandRequest) -> ActuatorCommandResponse:
        cmd = req.command.upper()
        if cmd in ["UNLOCK", "RELEASE"]:
            self.is_locked = False
            self.get_logger().error(f"[{self.device_id}] FAIL-SAFE: Electromagnetic emergency exit lock RELEASED/UNLOCKED.")
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state="UNLOCKED", message="Door unlocked.")
        elif cmd in ["LOCK", "ENGAGE"]:
            self.is_locked = True
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state="LOCKED", message="Door locked.")
        return ActuatorCommandResponse(success=False, actuator_id=self.device_id, current_state="LOCKED" if self.is_locked else "UNLOCKED", message="Unknown command.")


class CameraVisionNode(LifecycleNode):
    """[#12, #13, #17] Video Camera & Edge Vision Analytics Actuator."""
    def __init__(self, node_name: str = "camera_vision"):
        super().__init__(node_name)
        self.device_id = "security_camera_01"
        self.location = "main_entrance"
        self.recording_fps = 5  # Idle standby 5 FPS
        self.high_fps_recording = False
        self.detected_objects: List[str] = []
        self.confidences: List[float] = []

        self.vision_pub = self.create_publisher(VisionDetectionMsg, "/camera/detections", QoSProfile(depth=10))
        self.create_service(PollSensorResponse, f"/device/{self.device_id}/poll", self.handle_poll)
        self.create_service(ActuatorCommandResponse, f"/actuators/{self.device_id}/command", self.handle_command)

    def trigger_intruder_detection(self):
        self.detected_objects = ["person", "unidentified_face"]
        self.confidences = [0.94, 0.89]
        self.high_fps_recording = True
        self.recording_fps = 30
        self.get_logger().warn(f"[{self.device_id}] Edge Vision: Intruder identified! High-FPS (30fps) recording activated.")
        self._publish_detections(intrusion=True, fire=False)

    def trigger_visual_fire_detection(self):
        self.detected_objects = ["smoke_plume", "flame"]
        self.confidences = [0.96, 0.98]
        self.high_fps_recording = True
        self.recording_fps = 30
        self.get_logger().error(f"[{self.device_id}] Edge Vision: Flame & Smoke Plume identified visually!")
        self._publish_detections(intrusion=False, fire=True)

    def _publish_detections(self, intrusion: bool, fire: bool):
        msg = VisionDetectionMsg(
            camera_id=self.device_id,
            detected_classes=self.detected_objects,
            confidences=self.confidences,
            intrusion_confirmed=intrusion,
            visual_fire_confirmed=fire,
            bounding_boxes_json=json.dumps([{"cls": c, "conf": s} for c, s in zip(self.detected_objects, self.confidences)])
        )
        self.vision_pub.publish(msg)

    def handle_poll(self, req: PollSensorRequest) -> PollSensorResponse:
        return PollSensorResponse(
            success=True,
            device_id=self.device_id,
            values=[float(self.recording_fps), float(len(self.detected_objects))],
            value_keys=["recording_fps", "detected_object_count"],
            status_message=f"Recording: {'30 FPS (Alarm)' if self.high_fps_recording else '5 FPS (Idle)'}"
        )

    def handle_command(self, req: ActuatorCommandRequest) -> ActuatorCommandResponse:
        cmd = req.command.upper()
        if cmd == "RECORD_HIGH_FPS":
            self.high_fps_recording = True
            self.recording_fps = 30
            self.get_logger().warn("Camera switched to High-FPS 30fps forensic recording mode.")
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state="RECORDING_30FPS", message="High-fps active.")
        elif cmd == "STANDBY":
            self.high_fps_recording = False
            self.recording_fps = 5
            self.detected_objects = []
            return ActuatorCommandResponse(success=True, actuator_id=self.device_id, current_state="STANDBY_5FPS", message="Camera standby.")
        return ActuatorCommandResponse(success=False, actuator_id=self.device_id, current_state="IDLE", message="Unknown command.")
