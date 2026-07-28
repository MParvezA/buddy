# Low-rate system summary used by task policy, dialogue, and operators.

uint8 MODE_BOOTING=0
uint8 MODE_IDLE=1
uint8 MODE_ACTIVE=2
uint8 MODE_DOCKING=3
uint8 MODE_LOW_BATTERY=4
uint8 MODE_DEGRADED=5
uint8 MODE_FAULT=6
uint8 MODE_EMERGENCY_STOP=7

uint8 LOCALIZATION_UNKNOWN=0
uint8 LOCALIZATION_UNAVAILABLE=1
uint8 LOCALIZATION_DEGRADED=2
uint8 LOCALIZATION_GOOD=3

std_msgs/Header header
uint8 mode
uint8 localization_state
buddy_interfaces/SafetyState safety
float32 battery_percent
bool battery_state_known
bool motion_ready
string current_location
string current_task
string[] available_capabilities

