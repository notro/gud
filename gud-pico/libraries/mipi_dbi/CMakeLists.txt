add_library(mipi_dbi INTERFACE)

target_sources(mipi_dbi INTERFACE
  ${CMAKE_CURRENT_LIST_DIR}/mipi_dbi.c
)

target_include_directories(mipi_dbi INTERFACE ${CMAKE_CURRENT_LIST_DIR})
target_link_libraries(mipi_dbi INTERFACE hardware_spi hardware_gpio hardware_dma)
