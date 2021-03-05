cmake_minimum_required(VERSION 3.13)

set(TINYUSB_DEBUG_LEVEL 2)

include(pico_sdk_import.cmake)

project(gud_tusb_project)

pico_sdk_init()

add_executable(gud_tusb
	main.c
	usb_descriptors.c
	driver.c
	gud.c
	mipi_dbi.c
	lz4.c
)

target_include_directories(gud_tusb PRIVATE ${CMAKE_CURRENT_LIST_DIR})

target_link_libraries(gud_tusb PRIVATE pico_stdlib tinyusb_device tinyusb_board hardware_spi hardware_pwm hardware_dma pico_unique_id)
pico_add_extra_outputs(gud_tusb)
