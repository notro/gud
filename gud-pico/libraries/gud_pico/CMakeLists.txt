add_library(gud_pico INTERFACE)

target_sources(gud_pico INTERFACE
  ${CMAKE_CURRENT_LIST_DIR}/usb_descriptors.c
  ${CMAKE_CURRENT_LIST_DIR}/driver.c
  ${CMAKE_CURRENT_LIST_DIR}/gud.c
  ${CMAKE_CURRENT_LIST_DIR}/lz4.c
)

target_include_directories(gud_pico INTERFACE ${CMAKE_CURRENT_LIST_DIR})
target_link_libraries(gud_pico INTERFACE pico_stdlib tinyusb_device tinyusb_board pico_unique_id)
