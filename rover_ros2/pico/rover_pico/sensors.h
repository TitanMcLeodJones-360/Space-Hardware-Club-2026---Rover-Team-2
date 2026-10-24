#pragma once
#include <Wire.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_BMP3XX.h>
#include <cmath>
#include "config.h"

struct SensorData {
    float temperature = NAN;
    float pressure = NAN;
    float accel_x = NAN, accel_y = NAN, accel_z = NAN;
    float altitude = NAN;
};

class Sensors {
public:
    bool imu_ready = false, bmp_ready = false;
    const char *error = "Sensors disabled in config.h";

    bool begin() {
        if (!USE_SENSORS) return false;
        if (!Wire.setSDA(I2C_SDA_PIN) || !Wire.setSCL(I2C_SCL_PIN)) {
            error = "Invalid Wire I2C0 pin pair";
            return false;
        }
        Wire.begin();
        Wire.setClock(100000);
        imu_started = bno.begin();
        bmp_started = bmp.begin_I2C(BMP388_ADDRESS, &Wire);
        imu_ready = imu_started;
        bmp_ready = bmp_started;
        if (bmp_started) {
            bmp.setTemperatureOversampling(BMP3_OVERSAMPLING_2X);
            bmp.setPressureOversampling(BMP3_OVERSAMPLING_4X);
            bmp.setIIRFilterCoeff(BMP3_IIR_FILTER_COEFF_3);
            bmp.setOutputDataRate(BMP3_ODR_25_HZ);
        }
        error = imu_ready && bmp_ready ? "" : "A sensor did not initialize; check wiring/address";
        return imu_ready && bmp_ready;
    }

    SensorData read() {
        SensorData result;
        imu_ready = false;
        bmp_ready = false;
        if (!USE_SENSORS) return result;
        if (imu_started) {
            Wire.beginTransmission(BNO055_ADDRESS);
            if (Wire.endTransmission() == 0) {
                const auto acceleration = bno.getVector(Adafruit_BNO055::VECTOR_ACCELEROMETER);
                result.accel_x = acceleration.x();
                result.accel_y = acceleration.y();
                result.accel_z = acceleration.z();
                imu_ready = std::isfinite(result.accel_x) &&
                            std::isfinite(result.accel_y) && std::isfinite(result.accel_z);
            }
        }
        if (bmp_started && bmp.performReading()) {
            result.temperature = bmp.temperature;
            result.pressure = bmp.pressure / 1000.0f; // Pa to kPa for the GUI.
            if (bmp.pressure > 0 && SEA_LEVEL_PRESSURE_HPA > 0)
                result.altitude = 44330.0f * (1.0f - std::pow(
                    bmp.pressure / (SEA_LEVEL_PRESSURE_HPA * 100.0f), 0.1903f));
            bmp_ready = std::isfinite(result.temperature) && std::isfinite(result.pressure)
                        && std::isfinite(result.altitude);
        }
        error = imu_ready && bmp_ready ? "" : "Sensor data incomplete";
        return result;
    }

private:
    Adafruit_BNO055 bno{55, BNO055_ADDRESS, &Wire};
    Adafruit_BMP3XX bmp;
    bool imu_started = false, bmp_started = false;
};
