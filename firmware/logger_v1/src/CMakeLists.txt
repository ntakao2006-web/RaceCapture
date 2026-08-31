file(GLOB LOGGER_SOURCES "${CMAKE_CURRENT_LIST_DIR}/*.cpp")
idf_component_register(SRCS ${LOGGER_SOURCES}
  INCLUDE_DIRS "."
  REQUIRES driver esp_driver_sdmmc esp_driver_tsens esp_timer
           espressif__esp_tinyusb fatfs sdmmc nvs_flash logger_lua)
