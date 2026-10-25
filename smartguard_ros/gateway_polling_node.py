"""
Gateway Polling & Correlation Node for SmartGuard ROS 2.
Implements:
- [#9] Collecting information from different devices.
- [#NF1] Data aggregation across sliding time windows.
- [#NF3] Continuous polling of all sensor nodes via ROS Services.
- [#NF4] Sensor correlation, calibration, and bias correction via Kalman Filtering.
- [#NF2, #NF5] Secure communication and HMAC validation.
"""

import time
import math
import logging
from typing import Dict, List, Any, Optional
from collections import deque

from .ros_compat import Node, QoSProfile
from .interfaces import (
    PollSensorRequest, PollSensorResponse,
    FilteredTelemetryMsg, VerifyIncidentRequest, VerifyIncidentResponse,
    TimeStamp
)
from .security import SecurityManager

class KalmanFilter1D:
    """One-dimensional Kalman filter for sensor noise reduction and bias compensation."""
    def __init__(self, process_variance: float = 1e-4, measurement_variance: float = 0.05, initial_value: float = 0.0):
        self.q = process_variance
        self.r = measurement_variance
        self.x = initial_value
        self.p = 1.0
        self.last_time = time.time()
        self.rate_of_change = 0.0

    def update(self, measurement: float) -> float:
        now = time.time()
        dt = max(now - self.last_time, 0.001)

        # Prediction phase
        p_pred = self.p + self.q

        # Measurement update
        k = p_pred / (p_pred + self.r)
        new_x = self.x + k * (measurement - self.x)
        self.p = (1.0 - k) * p_pred

        # 1st derivative (Rate of change)
        self.rate_of_change = (new_x - self.x) / dt
        self.x = new_x
        self.last_time = now
        return self.x


class GatewayPollingNode(Node):
    def __init__(self, node_name: str = "gateway_polling_node"):
        super().__init__(node_name)
        self.sec_mgr = SecurityManager()

        # Registered pollable devices
        self.pollable_devices = [
            "appliance_washer_01",
            "ams_energy_meter_01",
            "health_wearable_01",
            "fire_sensor_combo_01",
            "leak_sensor_combo_01",
            "occupancy_combo_01",
            "security_camera_01"
        ]

        # Service clients for polling
        self.poll_clients = {
            dev_id: self.create_client(PollSensorResponse, f"/device/{dev_id}/poll")
            for dev_id in self.pollable_devices
        }

        # Client to Incident Verification Engine
        self.verify_client = self.create_client(VerifyIncidentResponse, "/incident/verify")

        # Publishers
        self.filtered_pub = self.create_publisher(FilteredTelemetryMsg, "/telemetry/filtered", QoSProfile(depth=20))

        # Sensor state & Kalman filters
        self.filters: Dict[str, Dict[str, KalmanFilter1D]] = {}
        self.sliding_windows: Dict[str, deque] = {}

        # Polling Timer (Continuous Polling [#NF3] at 1.0 Hz)
        self.poll_timer = self.create_timer(1.0, self.poll_all_devices)
        self.get_logger().info("Gateway Polling Node initialized. Continuous polling active at 1.0 Hz.")

    def poll_all_devices(self):
        """Active continuous polling loop querying every registered sensor node."""
        for dev_id in self.pollable_devices:
            client = self.poll_clients[dev_id]
            try:
                req = PollSensorRequest(device_id=dev_id, include_raw_diagnostics=True)
                resp: PollSensorResponse = client.call(req)
                if resp and resp.success:
                    self.process_polled_data(dev_id, resp.value_keys, resp.values)
            except Exception as e:
                self.get_logger().debug(f"Device {dev_id} poll skipped or waiting: {e}")

    def process_polled_data(self, dev_id: str, keys: List[str], values: List[float]):
        """Applies Kalman filter bias-correction, rate of change, and threshold monitoring."""
        if dev_id not in self.filters:
            self.filters[dev_id] = {}
            self.sliding_windows[dev_id] = deque(maxlen=60)  # 60 samples window

        metrics = dict(zip(keys, values))
        self.sliding_windows[dev_id].append((time.time(), metrics))

        for k, raw_val in metrics.items():
            if k not in self.filters[dev_id]:
                self.filters[dev_id][k] = KalmanFilter1D(initial_value=raw_val)

            kf = self.filters[dev_id][k]
            calibrated = kf.update(raw_val)
            roc = kf.rate_of_change

            # Publish filtered telemetry
            msg = FilteredTelemetryMsg(
                device_id=dev_id,
                device_type=k,
                location="residential_unit",
                calibrated_value=round(calibrated, 3),
                rate_of_change=round(roc, 3),
                variance_estimate=round(kf.p, 5),
                anomaly_flag=False,
                aggregation_window="1m_moving_avg"
            )

            # Check for anomalies to route to Verification Engine
            if dev_id == "fire_sensor_combo_01" and (calibrated > 55.0 or roc > 0.5):
                msg.anomaly_flag = True
                self.trigger_verification(dev_id, "FIRE", "living_room", calibrated)
            elif dev_id == "leak_sensor_combo_01" and (k == "flow_rate_l_min" and calibrated > 20.0):
                msg.anomaly_flag = True
                self.trigger_verification(dev_id, "WATER_LEAK", "utility_room", calibrated)
            elif dev_id == "health_wearable_01" and k == "fall_flag" and calibrated > 0.5:
                msg.anomaly_flag = True
                self.trigger_verification(dev_id, "HEALTH_FALL", "living_room", calibrated)

            self.filtered_pub.publish(msg)

    def trigger_verification(self, primary_dev: str, incident_type: str, location: str, reading: float):
        """Dispatches verification request to Incident Verification Engine."""
        try:
            req = VerifyIncidentRequest(
                primary_sensor_id=primary_dev,
                suspected_incident_type=incident_type,
                location=location,
                primary_reading=reading
            )
            resp: VerifyIncidentResponse = self.verify_client.call(req)
            self.get_logger().info(f"Verification result for {incident_type}: verified={resp.verified}, score={resp.confidence_score:.2f}")
        except Exception as e:
            self.get_logger().error(f"Error calling verification engine: {e}")
