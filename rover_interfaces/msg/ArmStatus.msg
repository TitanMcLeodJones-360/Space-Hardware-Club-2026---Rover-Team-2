bool ready
bool enabled
string mode
string bridge_mode
bool operator_online
bool pico_online
string note
string error

# These arrays use the same joint order. Targets are not measured positions.
string[] joint_names
float64[] target_deg
float64[] min_deg
float64[] max_deg

bool motor_ready
float64 motor_speed
float64 motor_limit
bool imu_ready
bool bmp_ready
bool sd_ready
uint32 sd_rows
string sd_file
string sensor_error
string sd_error
