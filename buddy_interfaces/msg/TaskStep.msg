# One bounded capability invocation in a task plan.

uint8 ON_FAILURE_ABORT=0
uint8 ON_FAILURE_CONTINUE=1

unique_identifier_msgs/UUID step_id
string capability
buddy_interfaces/TaskArgument[] arguments
builtin_interfaces/Duration timeout
uint8 on_failure

