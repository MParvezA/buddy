cmake_minimum_required(VERSION 3.8)
project(buddy_interfaces)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(unique_identifier_msgs REQUIRED)

set(message_files
  "msg/CapabilityArgument.msg"
  "msg/CapabilityDescriptor.msg"
  "msg/EmergencyStopRequest.msg"
  "msg/NamedLocation.msg"
  "msg/ObjectObservation.msg"
  "msg/RecognizedUtterance.msg"
  "msg/RobotStatus.msg"
  "msg/SafetyState.msg"
  "msg/TaskArgument.msg"
  "msg/TaskPlan.msg"
  "msg/TaskStep.msg"
  "msg/TaskStepResult.msg"
  "msg/WorldSummary.msg"
)

set(service_files
  "srv/ListCapabilities.srv"
  "srv/ResetEmergencyStop.srv"
  "srv/ResolveNamedLocation.srv"
)

set(action_files
  "action/ExecuteTask.action"
  "action/NavigateToNamedLocation.action"
  "action/Speak.action"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${message_files}
  ${service_files}
  ${action_files}
  DEPENDENCIES
    builtin_interfaces
    geometry_msgs
    std_msgs
    unique_identifier_msgs
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()

