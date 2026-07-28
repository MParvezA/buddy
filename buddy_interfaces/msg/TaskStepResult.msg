# Structured result for one capability invocation.

uint8 OUTCOME_SUCCEEDED=0
uint8 OUTCOME_CANCELLED=1
uint8 OUTCOME_REJECTED=2
uint8 OUTCOME_TIMED_OUT=3
uint8 OUTCOME_FAILED=4

unique_identifier_msgs/UUID step_id
string capability
uint8 outcome
uint16 error_code
string message

