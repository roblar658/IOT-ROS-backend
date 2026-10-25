# DeviceStatus.msg
# Lifecycle status of an individual smart home node or hardware module

builtin_interfaces/Time stamp
string device_id
string device_type
string lifecycle_state        # "UNCONFIGURED", "INACTIVE", "ACTIVE", "FINALIZED"
bool operational
float64 battery_level_pct
float64 power_consumption_w
string firmware_version
uint32 error_code
