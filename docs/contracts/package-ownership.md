# Package Ownership and Dependency Rules

## Repository layout

ROS packages live directly under the repository root so each parallel worktree
has a simple, disjoint path allowlist.

## Root-owned paths

- `buddy_interfaces/**`
- `buddy_bringup/**`
- `.github/**`
- Repository-root configuration and dependency files
- `docs/contracts/**`
- Repository-wide integration tests

## Workstream ownership

| Workstream | Allowed paths |
| --- | --- |
| Voice | `buddy_voice/**` |
| AI and dialogue | `buddy_brain/**` |
| Task executive | `buddy_task_executor/**`, `buddy_capabilities/**` |
| Navigation/perception | `buddy_navigation/**`, `buddy_localization/**`, `buddy_mapping/**`, `buddy_perception/**`, `buddy_world_model/**` |
| Safety/motion | `buddy_base/**`, `buddy_safety/**` |
| Gazebo/hardware | `buddy_description/**`, `buddy_gazebo/**`, `buddy_hardware/**` |

Workers may read the whole repository but only write their allowed paths.

## Dependency direction

Every workstream may depend on `buddy_interfaces` and standard ROS packages.
No workstream may import another workstream's implementation modules.

```text
voice ────────────────┐
AI/dialogue ──────────┤
task/capabilities ────┼──→ buddy_interfaces ←── standard ROS interfaces
navigation/perception ┤
safety/motion ────────┤
Gazebo/hardware ──────┘
```

Runtime composition through ROS topics, services, actions, and TF is allowed.
Build-time cycles are forbidden.

`buddy_bringup` is the root-owned composition package. Worker packages provide
their own bounded launch fragments and configuration but do not modify global
bringup.

## Shared-file rules

- Do not edit another workstream's package.
- Do not modify root-owned paths from a worker.
- Do not run repository-wide formatters from a worker.
- Do not modify shared dependency or CI files from a worker.
- Do not merge or rebase another worker branch.
- Do not create an implementation import to bypass a missing ROS contract.

