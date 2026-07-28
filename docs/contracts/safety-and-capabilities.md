# Safety and Capability Semantics

## Command arbitration

Publishers do not choose their own priority. Priority is fixed by the arbiter's
configuration:

| Priority | Source |
| ---: | --- |
| 250 | Safety stop override |
| 200 | Teleoperation |
| 150 | Docking |
| 125 | Bounded recovery |
| 100 | Navigation |

Emergency stop is outside normal arbitration and forces zero output.

Only a fresh request from the highest-priority eligible source is selected.
The initial freshness timeout is 250 ms and remains configurable. When no
eligible request is fresh, the arbiter outputs zero velocity.

## Safety state

- Startup state is motion-inhibited.
- `NORMAL` permits configured motion.
- `LIMITED` permits motion after applying reduced limits.
- `SOFT_STOPPED` commands zero motion but is not a latched emergency.
- `EMERGENCY_STOPPED` commands zero motion and remains latched.
- `FAULT` commands zero motion until the fault and reset requirements clear.

Every input and output command is timestamped. Stale or future-invalid commands
are rejected.

## Emergency stop

Any `EmergencyStopRequest` latches emergency stop and immediately commands zero
motion.

Reset uses the separate `ResetEmergencyStop` service and succeeds only when:

- `operator_acknowledged` is true;
- any physical emergency-stop input is released;
- motion-critical faults are cleared;
- required safety sensors are healthy;
- the caller is an allowed reset source.

Resetting the software latch does not bypass a physical motor-power interlock.

The initial deterministic spoken word "stop" is treated as an emergency-stop
request. A conversational "cancel the current task" is a normal task
cancellation and produces a soft stop.

## Initial capability contracts

### `stop`

- Arguments: none
- Effect: cancel active tasks and request a soft stop
- Preconditions: none
- Does not reset or weaken emergency stop

### `speak`

- Required argument: `text` (`string`)
- Optional argument: `voice` (`string`)
- Preconditions: speech service available
- Does not require motion or localization

### `navigate_to`

- Required argument: `location` (`string`)
- Preconditions: named location exists, localization is good, safety permits
  motion, navigation is available
- Executes `NavigateToNamedLocation`

### `report_status`

- Arguments: none
- Preconditions: status summary available
- Does not require motion or localization

## Task validation

Before accepting `ExecuteTask`, the task executive validates:

- Non-empty plan and unique non-zero IDs.
- Known and currently available capabilities.
- Exact argument names with no duplicates.
- Required arguments.
- Argument type and allowed values.
- Timeout bounds.
- Confirmation requirements.
- Current robot, safety, localization, and battery state.

Unknown capabilities, unknown arguments, invalid values, and unmet
preconditions are rejected before execution.

## Initial error-code ranges

| Range | Owner |
| --- | --- |
| `0` | No error |
| `1000–1999` | Voice |
| `2000–2999` | AI/dialogue |
| `3000–3999` | Task/capability |
| `4000–4999` | Navigation/perception |
| `5000–5999` | Safety/motion |
| `6000–6999` | Gazebo/hardware |
| `9000–9999` | Integration/supervisor |

Workstreams document their assigned codes without renumbering another range.

