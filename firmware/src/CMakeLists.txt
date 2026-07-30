# This file was automatically generated for projects
# without default 'CMakeLists.txt' file.

FILE(GLOB_RECURSE app_sources ${CMAKE_SOURCE_DIR}/src/*.*)

# 1-4-2: S3のみTinyUSB CDC(espressif/esp_tinyusb, idf_component.yml経由で取得)を使う。
# C3ではrules指定によりそもそもこの依存が解決されないため、REQUIRESもS3限定にする。
# 1-2-3: SDカード(SDMMC 4bit)書き込みもC3にはSDMMCホストペリフェラルが無いため
# S3限定(firmware/sd_card_test/src/CMakeLists.txtのREQUIRESに倣う)。
idf_build_get_property(rcp_idf_target IDF_TARGET)
set(rcp_extra_requires "")
if(rcp_idf_target STREQUAL "esp32s3")
    list(APPEND rcp_extra_requires espressif__esp_tinyusb esp_driver_sdmmc sdmmc fatfs driver)
endif()

idf_component_register(SRCS ${app_sources} REQUIRES ${rcp_extra_requires})
