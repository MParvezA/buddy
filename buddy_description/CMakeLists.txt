cmake_minimum_required(VERSION 3.16)
project(buddy_description)

find_package(ament_cmake REQUIRED)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

install(DIRECTORY urdf config DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_program(XACRO_EXECUTABLE xacro REQUIRED)
  add_test(NAME buddy_xacro_model
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test/test_xacro.py
            ${XACRO_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/urdf/buddy.urdf.xacro)
  set(BUDDY_GAZEBO_SDF
    ${CMAKE_CURRENT_SOURCE_DIR}/../buddy_gazebo/models/buddy/model.sdf)
  add_test(NAME buddy_description_simulation_parity
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test/test_xacro.py
            ${XACRO_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/urdf/buddy.urdf.xacro
            ${BUDDY_GAZEBO_SDF})
endif()

ament_package()
