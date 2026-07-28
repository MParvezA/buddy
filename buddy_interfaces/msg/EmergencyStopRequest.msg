# One-way request to latch the software emergency stop.
# Clearing the latch is intentionally a separate service.

uint8 REASON_UNSPECIFIED=0
uint8 REASON_VOICE_COMMAND=1
uint8 REASON_PHYSICAL_INPUT=2
uint8 REASON_COLLISION_RISK=3
uint8 REASON_WATCHDOG=4
uint8 REASON_OPERATOR=5
uint8 REASON_SYSTEM_FAULT=6

std_msgs/Header header
unique_identifier_msgs/UUID request_id
string source
uint8 reason_code
string reason

