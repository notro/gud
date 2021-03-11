cmake_minimum_required(VERSION 3.13)

set(TINYUSB_DEBUG_LEVEL 2)

include(pico_sdk_import.cmake)

project(pico_display_project)

pico_sdk_init()

add_subdirectory(libraries/gud_pico)
add_subdirectory(libraries/mipi_dbi)
add_subdirectory(examples)
