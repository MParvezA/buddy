# Authoritative, latched safety state.

uint8 STATE_NORMAL=0
uint8 STATE_LIMITED=1
uint8 STATE_SOFT_STOPPED=2
uint8 STATE_EMERGENCY_STOPPED=3
uint8 STATE_FAULT=4

uint16 REASON_NONE=0
uint16 REASON_STARTUP_INHIBIT=1
uint16 REASON_COMMAND_TIMEOUT=2
uint16 REASON_COLLISION_RISK=3
uint16 REASON_EMERGENCY_REQUEST=4
uint16 REASON_SENSOR_UNHEALTHY=5
uint16 REASON_CONTROLLER_FAULT=6
uint16 REASON_LOCALIZATION_LOST=7
uint16 REASON_OPERATOR=8

std_msgs/Header header
uint8 state
uint16 reason_code
bool motion_permitted
bool emergency_stop_latched
string source
string message

