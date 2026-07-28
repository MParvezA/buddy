cmake_minimum_required(VERSION 3.8)
project(buddy_mapping)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(mapping_config test/test_mapping_config.py)
endif()

ament_package()
