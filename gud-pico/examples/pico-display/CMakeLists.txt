add_executable(pico_display
  pico-display.c
)

target_include_directories(pico_display PRIVATE ${CMAKE_CURRENT_LIST_DIR})
target_link_libraries(pico_display PRIVATE pico_stdlib gud_pico mipi_dbi hardware_pwm pico_unique_id)
pico_add_extra_outputs(pico_display)
