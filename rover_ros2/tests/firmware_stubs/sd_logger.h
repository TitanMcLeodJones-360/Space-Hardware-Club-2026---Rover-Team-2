#pragma once
#include "sensors.h"
class SDLogger {
public:
    bool ready = false;
    uint32_t rows = 0;
    const char* filename = "LOG0000.CSV";
    const char* error = "";
    bool begin() { return ready = USE_SD; }
    bool write(uint32_t, const SensorData&) { if (!ready) return false; ++rows; return true; }
};
