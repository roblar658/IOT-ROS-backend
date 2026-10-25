# IncidentAlert.msg
# Alert payload emitted when an incident is detected or verified

builtin_interfaces/Time stamp
string alert_id
string incident_type          # "FIRE", "WATER_LEAK", "INTRUSION", "HEALTH_FALL", "ENERGY_OVERLOAD"
uint8 severity                # 0: INFO, 1: WARNING, 2: CRITICAL (Bypasses DND)
string location
float64 confidence_score       # Combined verification score (0.0 - 1.0)
string[] supporting_sensors   # IDs of multi-sensor corroborating sources
bool requires_emergency_dispatch
string description
