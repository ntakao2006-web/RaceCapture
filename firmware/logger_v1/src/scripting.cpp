#include "esp_heap_caps.h"
#include "esp_log.h"
#include "state.h"
#include <cstdio>
#include <new>
extern "C" {
#include "lauxlib.h"
#include "lua.h"
#include "lualib.h"
}

namespace logger {
static constexpr size_t LUA_BYTES = 512 * 1024;
struct LuaContext {
    size_t allocated = 0;
    uint64_t deadline = 0;
    unsigned tick_hz = 50;
    std::array<CanFrame, 256> pending[2];
    unsigned read[2]{}, write[2]{};
};
static LuaContext *context = nullptr; // only the Lua task accesses this
static void *allocate(void *ud, void *ptr, size_t old_size, size_t new_size) {
    auto &c = *static_cast<LuaContext *>(ud);
    if (!ptr)
        old_size = 0;
    if (!new_size) {
        heap_caps_free(ptr);
        c.allocated -= old_size;
        return nullptr;
    }
    if (new_size > LUA_BYTES || c.allocated - old_size > LUA_BYTES - new_size)
        return nullptr;
    void *p = heap_caps_realloc(ptr, new_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (p)
        c.allocated = c.allocated - old_size + new_size;
    return p;
}
static void deadlineHook(lua_State *L, lua_Debug *) {
    if (nowUs() > context->deadline)
        luaL_error(L, "script execution deadline exceeded");
}
static int add(lua_State *L) {
    const char *name = luaL_checkstring(L, 1);
    int rate = luaL_checkinteger(L, 2), precision = luaL_optinteger(L, 3, 2);
    double min = luaL_optnumber(L, 4, 0), max = luaL_optnumber(L, 5, 100);
    const char *unit = luaL_optstring(L, 6, "");
    int id;
    {
        Guard lock(state_mutex);
        id = addChannel(name, unit, min, max, precision, rate);
    }
    if (id < 0)
        return luaL_error(L, "invalid, conflicting or excessive channel definition");
    lua_pushinteger(L, id + 1);
    return 1;
}
static int channelId(lua_State *L, int argument) {
    if (lua_type(L, argument) == LUA_TNUMBER)
        return int(lua_tointeger(L, argument)) - 1;
    const char *name = luaL_checkstring(L, argument);
    Guard lock(state_mutex);
    return findChannel(name);
}
static int get(lua_State *L) {
    int id = channelId(L, 1);
    bool valid = false;
    double value = 0;
    {
        Guard lock(state_mutex);
        if (id >= 0 && size_t(id) < channel_count) {
            auto &c = channels[id];
            value = c.value;
            valid = c.available && fresh(nowUs(), c.updated_us, c.stale_ms);
        }
    }
    if (valid)
        lua_pushnumber(L, value);
    else
        lua_pushnil(L);
    return 1;
}
static bool writable(int id) {
    return id >= BASE_CHANNELS || id == RPM || id == SPEED || id == WATER_TEMP || id == OIL_PRESS ||
           (id >= THROTTLE && id <= AFR_RAW) || id == CAN_GPIO || id == WHEEL_HZ;
}
static int set(lua_State *L) {
    int id = channelId(L, 1);
    bool available = !lua_isnil(L, 2);
    double value = available ? luaL_checknumber(L, 2) : 0;
    bool ok;
    {
        Guard lock(state_mutex);
        ok = id >= 0 && size_t(id) < channel_count && writable(id);
        if (ok)
            putChannel(id, value, nowUs(), available);
    }
    if (!ok)
        return luaL_error(L, "setChannel: read-only or missing channel");
    return 0;
}
static int tickRate(lua_State *L) {
    int rate = luaL_checkinteger(L, 1);
    if (rate < 1 || rate > 100)
        return luaL_error(L, "tick rate must be 1..100 Hz");
    context->tick_hz = rate;
    return 0;
}
static int uptime(lua_State *L) {
    lua_pushnumber(L, nowUs() / 1000.0);
    return 1;
}
static int rx(lua_State *L) {
    int bus = luaL_checkinteger(L, 1) - 1;
    if (bus < 0 || bus > 1)
        return luaL_error(L, "CAN bus must be 1 or 2");
    // Non-blocking by design; timeout parameter is accepted only when zero.
    if (luaL_optinteger(L, 2, 0) != 0)
        return luaL_error(L, "rxCAN timeout must be zero");
    auto &c = *context;
    if (c.read[bus] == c.write[bus])
        return 0;
    const CanFrame f = c.pending[bus][c.read[bus]++ % 256];
    lua_pushinteger(L, f.id);
    lua_pushinteger(L, f.extended ? 1 : 0);
    lua_newtable(L);
    for (unsigned i = 0; i < f.dlc && !f.rtr; ++i) {
        lua_pushinteger(L, f.data[i]);
        lua_rawseti(L, -2, i + 1);
    }
    lua_pushnumber(L, f.us);
    lua_pushboolean(L, f.rtr);
    return 5;
}
static void reportError(lua_State *L) {
    const char *error = lua_tostring(L, -1);
    {
        Guard lock(state_mutex);
        snprintf(lua_error, sizeof(lua_error), "%s",
                 error ? error : "Lua failed (non-string error)");
    }
    ESP_LOGE("lua", "%s", lua_error);
    ++stats.lua_errors;
    stats.lua_ok = false;
    lua_settop(L, 0);
}
static bool invoke(lua_State *L, int arguments, uint32_t budget_us) {
    context->deadline = nowUs() + budget_us;
    lua_sethook(L, deadlineHook, LUA_MASKCOUNT, 1000);
    int status = lua_pcall(L, arguments, 0, 0);
    lua_sethook(L, nullptr, 0, 0);
    if (status) {
        reportError(L);
        return false;
    }
    return true;
}
static void openSafeLibraries(lua_State *L) {
    // No os/io/package/debug/coroutines and no protected calls that could catch
    // deadline errors.
    const luaL_Reg libs[] = {{"", luaopen_base},
                             {LUA_TABLIBNAME, luaopen_table},
                             {LUA_STRLIBNAME, luaopen_string},
                             {LUA_MATHLIBNAME, luaopen_math},
                             {nullptr, nullptr}};
    for (auto p = libs; p->func; ++p) {
        lua_pushcfunction(L, p->func);
        lua_pushstring(L, p->name);
        lua_call(L, 1, 0);
    }
    for (const char *name :
         {"dofile", "loadfile", "load", "loadstring", "require", "module", "pcall", "xpcall",
          "getfenv", "setfenv", "collectgarbage", "print", "newproxy"}) {
        lua_pushnil(L);
        lua_setglobal(L, name);
    }
    lua_register(L, "addChannel", add);
    lua_register(L, "getChannel", get);
    lua_register(L, "setChannel", set);
    lua_register(L, "rxCAN", rx);
    lua_register(L, "setTickRate", tickRate);
    lua_register(L, "getUptime", uptime);
}
static void luaTask(void *) {
    void *memory = heap_caps_malloc(sizeof(LuaContext), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    ESP_ERROR_CHECK(memory ? ESP_OK : ESP_ERR_NO_MEM);
    context = new (memory) LuaContext{};
    char *text = static_cast<char *>(
        heap_caps_malloc(sizeof(script_text), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    ESP_ERROR_CHECK(context && text ? ESP_OK : ESP_ERR_NO_MEM);
    lua_State *L = nullptr;
    uint32_t revision = 0;
    uint64_t next = 0;
    while (true) {
        uint32_t wanted;
        {
            Guard lock(state_mutex);
            wanted = script_revision;
        }
        if (wanted != revision || stats.reload_lua.exchange(false)) {
            if (L)
                lua_close(L);
            L = nullptr;
            {
                Guard lock(state_mutex);
                strcpy(text, script_text);
                revision = script_revision;
                lua_error[0] = 0;
                for (size_t i = BASE_CHANNELS; i < channel_count; ++i)
                    channels[i].available = false;
            }
            context->read[0] = context->read[1] = context->write[0] = context->write[1] = 0;
            context->tick_hz = 50;
            stats.lua_ok = true;
            if (*text) {
                L = lua_newstate(allocate, context);
                if (!L) {
                    stats.lua_ok = false;
                    ++stats.lua_errors;
                } else {
                    openSafeLibraries(L);
                    if (static_cast<unsigned char>(text[0]) == 0x1b) {
                        lua_pushliteral(L, "Binary Lua chunks are not accepted");
                        reportError(L);
                    } else if (luaL_loadbuffer(L, text, strlen(text), "user"))
                        reportError(L);
                    else
                        invoke(L, 0, 50000);
                }
            }
        }
        CanFrame f;
        unsigned drained = 0;
        while (drained++ < 256 && xQueueReceive(lua_can_queue, &f, 0) == pdTRUE) {
            if (!L || !stats.lua_ok)
                continue;
            unsigned bus = f.bus - 1;
            if (bus > 1)
                continue;
            if (context->write[bus] - context->read[bus] >= 256) {
                ++stats.lua_drop;
                continue;
            }
            context->pending[bus][context->write[bus]++ % 256] = f;
        }
        if (L && stats.lua_ok && nowUs() >= next) {
            next = nowUs() + 1000000 / context->tick_hz;
            lua_getglobal(L, "onTick");
            if (lua_isfunction(L, -1))
                invoke(L, 0, 5000);
            else
                lua_pop(L, 1);
        }
        vTaskDelay(pdMS_TO_TICKS(2));
    }
}
void startLua() {
    ESP_ERROR_CHECK(xTaskCreate(luaTask, "lua", 16384, nullptr, 2, nullptr) == pdPASS
                        ? ESP_OK
                        : ESP_ERR_NO_MEM);
}
} // namespace logger
