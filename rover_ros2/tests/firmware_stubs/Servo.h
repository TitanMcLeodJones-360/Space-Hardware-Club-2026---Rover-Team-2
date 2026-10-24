#pragma once
class Servo {
    bool on = false;
public:
    int pin = -1, pulse = -1;
    bool attached() const { return on; }
    int attach(int p, int, int, int initial) { pin = p; pulse = initial; on = true; return p; }
    void detach() { on = false; }
    void writeMicroseconds(int value) { pulse = value; }
};
