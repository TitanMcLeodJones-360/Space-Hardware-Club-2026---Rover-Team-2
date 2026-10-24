#pragma once
#include <cstdint>
#include <string>
#include <map>
constexpr int OUTPUT = 1, LOW = 0, HIGH = 1;
inline uint32_t fake_time = 0;
inline std::map<int, int> digital_pins, pwm_pins;
inline uint32_t millis() { return fake_time; }
inline void pinMode(int, int) {}
inline void digitalWrite(int pin, int value) { digital_pins[pin] = value; }
inline void analogWrite(int pin, int value) { pwm_pins[pin] = value; }
inline void analogWriteFreq(int) {}
inline void analogWriteRange(int) {}
class Stream {
public:
    bool connected = true;
    std::string rx, tx;
    operator bool() const { return connected; }
    void begin(uint32_t) {}
    bool setTX(int) { return true; }
    bool setRX(int) { return true; }
    void setFIFOSize(int) {}
    int available() const { return static_cast<int>(rx.size()); }
    int read() { const char c = rx.front(); rx.erase(0, 1); return c; }
    size_t write(uint8_t c) { tx += static_cast<char>(c); return 1; }
    size_t write(const uint8_t* data, size_t count) {
        tx.append(reinterpret_cast<const char*>(data), count); return count;
    }
    void println() { tx += '\n'; }
};
inline Stream Serial, Serial1;
