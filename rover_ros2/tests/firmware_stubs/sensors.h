#pragma once
#include <cmath>
#include "config.h"
struct SensorData {
    float temperature = NAN, pressure = NAN, accel_x = NAN, accel_y = NAN,
          accel_z = NAN, altitude = NAN;
};
class Sensors {
public:
    bool imu_ready = false, bmp_ready = false;
    const char* error = "";
    int read_count = 0;
    bool begin() { return imu_ready = bmp_ready = USE_SENSORS; }
    SensorData read() { ++read_count; return {23.5f, 101.325f, .1f, -.2f, 9.81f, 42.f}; }
};
