#pragma once
#include <SPI.h>
#include <SD.h>
#include <cstdio>
#include <cstring>
#include "sensors.h"

class SDLogger {
public:
    bool ready = false;
    uint32_t rows = 0;
    char filename[16] = "";
    const char *error = "SD disabled in config.h";

    bool begin() {
        if (!USE_SD) return false;
        if (!USE_SENSORS) {
            error = "Enable sensors before SD logging";
            return false;
        }
        if (!SPI.setSCK(SD_SCK_PIN) || !SPI.setTX(SD_MOSI_PIN) || !SPI.setRX(SD_MISO_PIN)) {
            error = "Invalid SPI0 pin selection";
            return false;
        }
        if (!SD.begin(SD_CS_PIN, SPI)) {
            error = "SD mount failed; check SPI wiring and FAT32 format";
            return false;
        }
        for (int index = 0; index < 10000; ++index) {
            std::snprintf(filename, sizeof(filename), "LOG%04d.CSV", index);
            if (!SD.exists(filename)) {
                file = SD.open(filename, FILE_WRITE);
                if (!file) break;
                const char *header = "elapsed_ms,temperature_c,pressure_kpa,accel_x_m_s2,accel_y_m_s2,accel_z_m_s2,altitude_m\n";
                file.clearWriteError();
                const bool written = file.write(reinterpret_cast<const uint8_t *>(header),
                                                 std::strlen(header)) == std::strlen(header);
                file.flush();
                ready = written && file.getWriteError() == 0;
                error = ready ? "" : "SD header write failed";
                return ready;
            }
        }
        error = "Could not create an SD log file";
        return false;
    }

    bool write(uint32_t elapsed_ms, const SensorData &data) {
        if (!ready) return false;
        const float values[] = {data.temperature, data.pressure, data.accel_x,
                                data.accel_y, data.accel_z, data.altitude};
        char columns[6][24] = {};
        for (int i = 0; i < 6; ++i)
            if (std::isfinite(values[i])) std::snprintf(columns[i], sizeof(columns[i]), "%.4f", values[i]);
        char row[200];
        const int length = std::snprintf(row, sizeof(row), "%lu,%s,%s,%s,%s,%s,%s\n",
            static_cast<unsigned long>(elapsed_ms), columns[0], columns[1], columns[2],
            columns[3], columns[4], columns[5]);
        file.clearWriteError();
        const bool written = length > 0 && length < int(sizeof(row)) &&
            file.write(reinterpret_cast<const uint8_t *>(row), length) == size_t(length);
        file.flush(); // One row per second; keep the latest row on the card.
        if (!written || file.getWriteError() != 0) {
            ready = false;
            error = "SD write failed; restart after checking the card";
            file.close();
            return false;
        }
        ++rows;
        return true;
    }

private:
    File file;
};
