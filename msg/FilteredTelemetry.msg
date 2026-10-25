# FilteredTelemetry.msg
# Post-Kalman filter, bias-corrected and aggregated telemetry published by Gateway

builtin_interfaces/Time stamp
string device_id
string device_type
string location

float64 calibrated_value
float64 rate_of_change         # 1st derivative (dT/dt, dC/dt, dFlow/dt)
float64 variance_estimate      # Estimation error covariance from Kalman filter
bool anomaly_flag
string aggregation_window      # e.g., "1m_mean", "5m_moving_avg"
