cmake_minimum_required(VERSION 3.8)
project(buddy_safety)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ament_cmake REQUIRED)
find_package(buddy_interfaces REQUIRED)
find_package(diagnostic_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rcl_interfaces REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)

add_library(${PROJECT_NAME}_core
  src/command_arbiter_core.cpp
  src/safety_core.cpp
)
target_include_directories(${PROJECT_NAME}_core PUBLIC
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<INSTALL_INTERFACE:include/${PROJECT_NAME}>"
)
ament_target_dependencies(${PROJECT_NAME}_core
  buddy_interfaces
  geometry_msgs
  sensor_msgs
)

add_library(${PROJECT_NAME}_nodes
  src/command_arbiter_node.cpp
  src/safety_filter_node.cpp
)
target_include_directories(${PROJECT_NAME}_nodes PUBLIC
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<INSTALL_INTERFACE:include/${PROJECT_NAME}>"
)
target_link_libraries(${PROJECT_NAME}_nodes ${PROJECT_NAME}_core)
ament_target_dependencies(${PROJECT_NAME}_nodes
  buddy_interfaces
  diagnostic_msgs
  geometry_msgs
  rcl_interfaces
  rclcpp
  sensor_msgs
)

add_executable(command_arbiter src/command_arbiter_main.cpp)
target_link_libraries(command_arbiter ${PROJECT_NAME}_nodes)
ament_target_dependencies(command_arbiter rclcpp)

add_executable(safety_filter src/safety_filter_main.cpp)
target_link_libraries(safety_filter ${PROJECT_NAME}_nodes)
ament_target_dependencies(safety_filter rclcpp)

install(
  DIRECTORY include/
  DESTINATION include/${PROJECT_NAME}
)
install(
  DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)
install(
  TARGETS
    ${PROJECT_NAME}_core
    ${PROJECT_NAME}_nodes
    command_arbiter
    safety_filter
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME}
  INCLUDES DESTINATION include/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)

  ament_add_gtest(test_command_arbiter_core test/test_command_arbiter_core.cpp)
  target_link_libraries(test_command_arbiter_core ${PROJECT_NAME}_core)
  ament_target_dependencies(test_command_arbiter_core geometry_msgs)

  ament_add_gtest(test_safety_core test/test_safety_core.cpp)
  target_link_libraries(test_safety_core ${PROJECT_NAME}_core)
  ament_target_dependencies(test_safety_core buddy_interfaces geometry_msgs sensor_msgs)

  ament_add_gtest(test_motion_graph test/test_motion_graph.cpp TIMEOUT 30)
  target_link_libraries(test_motion_graph ${PROJECT_NAME}_nodes)
  ament_target_dependencies(test_motion_graph
    buddy_interfaces
    diagnostic_msgs
    geometry_msgs
    rclcpp
    sensor_msgs
  )
  set_tests_properties(
    test_motion_graph
    PROPERTIES ENVIRONMENT
      "ROS_LOG_DIR=/tmp/buddy_safety_test_logs;FASTDDS_BUILTIN_TRANSPORTS=SHM"
  )

  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_dependencies(
  buddy_interfaces
  diagnostic_msgs
  geometry_msgs
  rcl_interfaces
  rclcpp
  sensor_msgs
)
ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_package()
