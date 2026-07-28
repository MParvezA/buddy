cmake_minimum_required(VERSION 3.16)
project(buddy_gazebo)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
find_package(gz-sim8 REQUIRED)

add_library(buddy_command_watchdog SHARED
  src/command_watchdog.cpp
)
target_compile_features(buddy_command_watchdog PUBLIC cxx_std_17)
target_include_directories(buddy_command_watchdog PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(buddy_command_watchdog PUBLIC gz-sim8::gz-sim8)

ament_python_install_package(${PROJECT_NAME})

install(TARGETS buddy_command_watchdog
  EXPORT export_buddy_command_watchdog
  LIBRARY DESTINATION lib
)
install(DIRECTORY include/ DESTINATION include)
install(PROGRAMS buddy_gazebo/safe_cmd_vel_adapter.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME safe_cmd_vel_adapter
)
install(DIRECTORY config launch models worlds
  DESTINATION share/${PROJECT_NAME}
)
install(FILES README.md DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ros_gz_bridge REQUIRED)
  add_executable(command_watchdog_state_test
    test/command_watchdog_state_test.cpp
  )
  target_compile_features(command_watchdog_state_test PUBLIC cxx_std_17)
  target_include_directories(command_watchdog_state_test PRIVATE include)
  target_link_libraries(command_watchdog_state_test PRIVATE gz-sim8::gz-sim8)
  add_test(NAME command_watchdog_state COMMAND command_watchdog_state_test)
  add_executable(bridge_qos_config_test
    test/bridge_qos_config_test.cpp
  )
  target_compile_features(bridge_qos_config_test PUBLIC cxx_std_17)
  target_link_libraries(
    bridge_qos_config_test PRIVATE ros_gz_bridge::ros_gz_bridge)
  add_test(NAME bridge_qos_config
    COMMAND bridge_qos_config_test
            ${CMAKE_CURRENT_SOURCE_DIR}/config/bridge.yaml
  )
  add_test(NAME buddy_gazebo_model
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test/test_model.py
  )
endif()

ament_export_targets(export_buddy_command_watchdog HAS_LIBRARY_TARGET)
ament_export_dependencies(gz-sim8)
ament_package()
