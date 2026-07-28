# Buddy ROS Contract

## Contract status

- Version: `0.1.0`
- Status: **FROZEN**
- Frozen for: Initial parallel implementation round
- Contract owner: Root coordinator

Workers may consume this contract but may not change it. A discovered problem
must be returned to the coordinator as a change request describing the exact
problem, affected workstreams, compatibility impact, and proposed migration.

## Contract documents

- [Repository inventory](repository-inventory.md)
- [Package ownership and dependency rules](package-ownership.md)
- [ROS interfaces](ros-interfaces.md)
- [TF, time, and QoS](tf-time-qos.md)
- [Safety and capability semantics](safety-and-capabilities.md)
- [Integration and validation](integration-validation.md)

The message, service, and action source of truth is
[`buddy_interfaces`](../../buddy_interfaces/).

## Compatibility rule

During the frozen round:

- Fields may not be removed, renamed, or retyped.
- Constants may not be renumbered.
- Topic, action, service, and frame names may not change.
- QoS reliability or durability may not be weakened.
- New optional interfaces require coordinator approval and a contract version
  update.
