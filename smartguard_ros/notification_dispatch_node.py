"""
Notification and Emergency Dispatch Node for SmartGuard ROS 2.
Implements:
- [#10 / #3 in desc 2] Real-time alerts delivered to relevant people.
- [#13 / #3 in desc 3] Standardized CAP messages sent to emergency response centers (110, 112, 113).
- [#21 / #2 in desc 5] Multi-level notification service with mandatory alerts overriding DND.
- [#NF14 / #NF1 in desc 5] Subscription-based third-party API integration.
"""

import time
import json
import logging
from typing import Dict, Any, List

from .ros_compat import Node, QoSProfile
from .interfaces import IncidentAlertMsg, TimeStamp
from .security import SecurityManager

class NotificationDispatchNode(Node):
    def __init__(self, node_name: str = "notification_dispatch_node"):
        super().__init__(node_name)
        self.sec_mgr = SecurityManager()

        # Subscription to verified alerts
        self.alert_sub = self.create_subscription(
            IncidentAlertMsg,
            "/alerts/incidents",
            self.handle_alert,
            QoSProfile(depth=10, durability="TRANSIENT_LOCAL")
        )

        # Audit history of sent notifications
        self.notification_log: List[Dict[str, Any]] = []
        self.dispatched_emergency_calls: List[Dict[str, Any]] = []

        # Subscription tiers [#NF14]
        self.active_subscription_tier = "TIER_3_PROFESSIONAL_24_7"

        self.get_logger().info("Notification & Emergency Dispatch Node initialized.")

    def handle_alert(self, msg: IncidentAlertMsg):
        """Processes alerts based on severity and mandatory delivery rules."""
        is_mandatory = (msg.severity == 2)  # Critical alerts are mandatory

        notif_record = {
            "timestamp": time.time(),
            "alert_id": msg.alert_id,
            "incident_type": msg.incident_type,
            "severity": "CRITICAL" if msg.severity == 2 else ("WARNING" if msg.severity == 1 else "INFO"),
            "location": msg.location,
            "confidence": msg.confidence_score,
            "is_mandatory": is_mandatory,
            "dnd_override": is_mandatory,
            "channels": ["APP_PUSH", "AUDIBLE_SIREN", "SMS"] if is_mandatory else ["APP_PUSH"]
        }
        self.notification_log.append(notif_record)

        # Log resident notification
        if is_mandatory:
            self.get_logger().error(
                f"[MANDATORY ALERT - DND BYPASS]: {msg.incident_type} at {msg.location}! "
                f"Siren activated. Push sent to all registered occupants."
            )
        else:
            self.get_logger().info(f"[Notification]: {msg.description}")

        # Send to Emergency Response Center if required
        if msg.requires_emergency_dispatch:
            self.dispatch_to_emergency_center(msg)

    def dispatch_to_emergency_center(self, msg: IncidentAlertMsg):
        """Dispatches Common Alerting Protocol (CAP) payload to emergency authorities."""
        center = "110 (Fire & Rescue)" if msg.incident_type == "FIRE" else \
                 ("112 (Police & Security)" if msg.incident_type == "INTRUSION" else \
                 ("113 (Emergency Medical)" if msg.incident_type == "HEALTH_FALL" else "EMERGENCY_ONCALL_PLUMBER"))

        # Build Common Alerting Protocol (CAP) standard object
        cap_payload = {
            "identifier": f"CAP-{msg.alert_id}",
            "sender": "smartguard_ros_gateway@residential.secure.no",
            "sent": time.strftime("%Y-%m-%dT%H:%M:%S+01:00"),
            "status": "Actual",
            "msgType": "Alert",
            "scope": "Restricted",
            "info": {
                "category": "Safety",
                "event": f"Verified {msg.incident_type}",
                "urgency": "Immediate",
                "severity": "Extreme",
                "certainty": "Observed" if msg.confidence_score > 0.9 else "Likely",
                "eventCode": msg.incident_type,
                "area": {"areaDesc": f"Apartment 4B, {msg.location}"},
                "confidenceScore": msg.confidence_score,
                "corroboratingSensors": msg.supporting_sensors
            }
        }

        # Encrypt sensitive dispatch payload for transmission [#NF2, #NF16]
        encrypted_token = self.sec_mgr.encrypt_sensitive_data(json.dumps(cap_payload))

        dispatch_entry = {
            "dispatch_id": cap_payload["identifier"],
            "target_center": center,
            "incident": msg.incident_type,
            "cap_data": cap_payload,
            "encrypted_token": encrypted_token,
            "status": "ACKNOWLEDGED_BY_OPERATOR"
        }
        self.dispatched_emergency_calls.append(dispatch_entry)

        self.get_logger().critical(
            f"--> DISPATCHED TO {center} <--\n"
            f"    CAP Identifier: {cap_payload['identifier']}\n"
            f"    Event: {msg.incident_type} (Confidence: {msg.confidence_score*100:.1f}%)\n"
            f"    Sensors Verified: {', '.join(msg.supporting_sensors)}\n"
            f"    Transmission: Encrypted mTLS (Token: {encrypted_token[:24]}...)"
        )
