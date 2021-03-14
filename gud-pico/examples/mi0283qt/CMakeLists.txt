add_executable(mi0283qt
  mi0283qt.c
)

target_include_directories(mi0283qt PRIVATE ${CMAKE_CURRENT_LIST_DIR})
target_link_libraries(mi0283qt PRIVATE pico_stdlib gud_pico mipi_dbi hardware_pwm pico_unique_id)
pico_add_extra_outputs(mi0283qt)
