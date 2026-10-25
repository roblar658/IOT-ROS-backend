# SensorTelemetry.msg
# Raw telemetry transmitted from smart home devices or sensor drivers

builtin_interfaces/Time stamp
string device_id
string device_type
string location

# Multi-metric raw payload (key-value or normalized numeric readings)
float64[] values
string[] value_keys
string raw_unit

# Security and integrity verification
string hmac_signature
uint32 sequence_number
