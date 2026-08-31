# Keep C-only Lua separate from the C++ application. PlatformIO merges an
# application's C and C++ warning options when both live in the main component.
file(GLOB LUA_SOURCES "${CMAKE_CURRENT_LIST_DIR}/../../../lib/lua/*.c")
idf_component_register(SRCS ${LUA_SOURCES} INCLUDE_DIRS "../../../lib/lua")
