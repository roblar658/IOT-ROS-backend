"""
Message, Service, and Action Interface structures for SmartGuard ROS 2.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time

@dataclass
class TimeStamp:
    sec: int = 0
    nanosec: int = 0

    @classmethod
    def now(cls):
        t = time.time()
        sec = int(t)
        nanosec = int((t - sec) * 1e9)
        return cls(sec=sec, nanosec=nanosec)

# ----------------- Messages -----------------

@dataclass
class SensorTelemetryMsg:
    stamp: TimeStamp = field(default_factory=TimeStamp.now)
    device_id: str = ""
    device_type: str = ""
    location: str = ""
    values: List[float] = field(default_factory=list)
    value_keys: List[str] = field(default_factory=list)
    raw_unit: str = ""
    hmac_signature: str = ""
    sequence_number: int = 0

@dataclass
class FilteredTelemetryMsg:
    stamp: TimeStamp = field(default_factory=TimeStamp.now)
    device_id: str = ""
    device_type: str = ""
    location: str = ""
    calibrated_value: float = 0.0
    rate_of_change: float = 0.0
    variance_estimate: float = 0.0
    anomaly_flag: bool = False
    aggregation_window: str = "1m_mean"

@dataclass
class IncidentAlertMsg:
    stamp: TimeStamp = field(default_factory=TimeStamp.now)
    alert_id: str = ""
    incident_type: str = ""          # FIRE, WATER_LEAK, INTRUSION, HEALTH_FALL, ENERGY_OVERLOAD
    severity: int = 1                # 0: INFO, 1: WARNING, 2: CRITICAL (Bypasses DND)
    location: str = ""
    confidence_score: float = 0.0
    supporting_sensors: List[str] = field(default_factory=list)
    requires_emergency_dispatch: bool = False
    description: str = ""

@dataclass
class DeviceStatusMsg:
    stamp: TimeStamp = field(default_factory=TimeStamp.now)
    device_id: str = ""
    device_type: str = ""
    lifecycle_state: str = "UNCONFIGURED"
    operational: bool = True
    battery_level_pct: float = 100.0
    power_consumption_w: float = 0.0
    firmware_version: str = "v2.1"
    error_code: int = 0

@dataclass
class EnergyStatusMsg:
    stamp: TimeStamp = field(default_factory=TimeStamp.now)
    total_grid_power_kw: float = 0.0
    grid_voltage_v: float = 230.0
    grid_frequency_hz: float = 50.0
    power_budget_limit_kw: float = 10.0
    peak_shaving_active: bool = False
    throttled_appliances: List[str] = field(default_factory=list)
    battery_storage_pct: float = 95.0

@dataclass
class HealthVitalsMsg:
    stamp: TimeStamp = field(default_factory=TimeStamp.now)
    occupant_id: str = ""
    heart_rate_bpm: float = 72.0
    blood_oxygen_spo2: float = 98.0
    skin_temperature_c: float = 36.6
    fall_detected: bool = False
    impact_force_g: float = 1.0
    activity_state: str = "RESTING"

@dataclass
class VisionDetectionMsg:
    stamp: TimeStamp = field(default_factory=TimeStamp.now)
    camera_id: str = ""
    detected_classes: List[str] = field(default_factory=list)
    confidences: List[float] = field(default_factory=list)
    intrusion_confirmed: bool = False
    visual_fire_confirmed: bool = False
    bounding_boxes_json: str = "[]"

# ----------------- Services -----------------

@dataclass
class PollSensorRequest:
    device_id: str
    include_raw_diagnostics: bool = False

@dataclass
class PollSensorResponse:
    success: bool
    device_id: str
    values: List[float]
    value_keys: List[str]
    status_message: str
    measurement_time: TimeStamp = field(default_factory=TimeStamp.now)

@dataclass
class VerifyIncidentRequest:
    primary_sensor_id: str
    suspected_incident_type: str
    location: str
    primary_reading: float

@dataclass
class VerifyIncidentResponse:
    verified: bool
    confidence_score: float
    verification_summary: str
    corroborating_sensors: List[str]
    recommended_emergency_action: str

@dataclass
class ManageDeviceRequest:
    action: str              # ADD, REMOVE, START, STOP, RESUME
    device_id: str
    device_type: str = ""
    configuration_json: str = "{}"

@dataclass
class ManageDeviceResponse:
    success: bool
    previous_state: str
    new_state: str
    message: str

@dataclass
class SetPowerBudgetRequest:
    max_power_limit_kw: float
    auto_shedding_enabled: bool = True

@dataclass
class SetPowerBudgetResponse:
    success: bool
    applied_limit_kw: float
    message: str

@dataclass
class ActuatorCommandRequest:
    target_actuator: str     # WATER_VALVE, EMERGENCY_LOCK, HVAC, LIGHTING, APPLIANCE
    command: str             # CLOSE, OPEN, UNLOCK, LOCK, STROBE, FULL_ON, OFF, SET_MODE
    payload_json: str = "{}"

@dataclass
class ActuatorCommandResponse:
    success: bool
    actuator_id: str
    current_state: str
    message: str

# ----------------- Actions -----------------

@dataclass
class EmergencyWorkflowGoal:
    workflow_name: str
    incident_type: str
    location: str
    confidence_score: float
    bypass_dnd_notifications: bool = True

@dataclass
class EmergencyWorkflowFeedback:
    current_step: str
    progress_ratio: float
    active_subsystem: str

@dataclass
class EmergencyWorkflowResult:
    success: bool
    completed_actions: List[str]
    actions_succeeded: int
    actions_failed: int
    emergency_dispatch_id: str
    total_execution_time_ms: float
    audit_summary: str

@dataclass
class PredictiveMaintenanceGoal:
    device_id: str
    sampling_window_sec: float = 5.0
    perform_fft_analysis: bool = True

@dataclass
class PredictiveMaintenanceFeedback:
    samples_processed_pct: float
    current_vibration_rms: float
    current_temp_c: float

@dataclass
class PredictiveMaintenanceResult:
    health_ok: bool
    wear_index: float
    dominant_frequency_hz: float
    harmonic_distortion: float
    estimated_days_remaining: int
    recommended_maintenance: str
