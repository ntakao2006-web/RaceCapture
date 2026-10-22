# This file was automatically generated for projects
# without default 'CMakeLists.txt' file.

idf_component_register(
    SRCS "main.cpp"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_driver_sdmmc
        esp_driver_tsens
        espressif__esp_tinyusb
        fatfs
        sdmmc
)
