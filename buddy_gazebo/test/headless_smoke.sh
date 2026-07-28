#!/usr/bin/env bash
set -euo pipefail

pkg_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
world="$pkg_dir/worlds/buddy_smoke.sdf"
export GZ_SIM_RESOURCE_PATH="$pkg_dir/models${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
gz sdf -k "$pkg_dir/models/buddy/model.sdf"
gz sim -s -r "$world" >"${TMPDIR:-/tmp}/buddy-gazebo-smoke.$$.log" 2>&1 &
gz_pid=$!
cleanup() { kill "$gz_pid" 2>/dev/null || true; wait "$gz_pid" 2>/dev/null || true; }
trap cleanup EXIT

for _ in $(seq 1 30); do
  if gz topic -l 2>/dev/null | grep -qx '/clock'; then break; fi
  sleep 0.2
done
topics="$(gz topic -l)"
for topic in /clock /model/buddy/cmd_vel /joint_state /lidar/scan /imu/data_raw /camera/image_raw /camera/camera_info; do
  grep -qx "$topic" <<<"$topics"
done
grep -q '/world/buddy_smoke/model/buddy/link/bumper_link/sensor/bumper/contact' <<<"$topics"
echo "Buddy Gazebo Harmonic headless smoke test passed"
