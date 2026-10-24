#include <cassert>
#include <iostream>
#include "rover_pico.ino"

void frame(const char* json) { Serial.rx += std::string(json) + "\n"; readCommands(); }
void heartbeat() { frame("{\"command\":\"HEARTBEAT\"}"); }
void enable() { heartbeat(); frame("{\"command\":\"ARM_ENABLE\"}"); }
int main() {
    setup();
    assert(arm.ready && !arm.enabled && sensors.imu_ready && sensors.bmp_ready && logger.ready);
    for (int i = 0; i < JOINT_COUNT; ++i) assert(!servos[i].attached() && servoPulse(i) == 1500);
    assert(pwm_pins[MOTOR_PWM_PIN] == 0);
    frame("{\"command\":\"ARM_ENABLE\"}");
    assert(!arm.enabled);
    enable();
    assert(arm.enabled);
    for (int i = 0; i < JOINT_COUNT; ++i)
        assert(servos[i].attached() && servos[i].pin == JOINTS[i].pin && servos[i].pulse == 1500);
    frame("{\"axis\":\"Axis1\",\"angle\":2}");
    frame("{\"axis\":\"Axis2\",\"angle\":-2}");
    frame("{\"axis\":\"Axis3A\",\"angle\":1}");
    frame("{\"axis\":\"Axis3B\",\"angle\":-1}");
    assert(servos[0].pulse == 1500); // Target changes are ramped by loop(), not applied abruptly.
    for (fake_time = 20; fake_time <= 1000; fake_time += 20) {
        if (fake_time % 200 == 0) heartbeat();
        loop();
    }
    assert(servos[0].pulse == 1520 && servos[1].pulse == 1480);
    assert(servos[2].pulse == 1510 && servos[3].pulse == 1490);
    assert(sensors.read_count == 5 && logger.rows == 1);
    assert(Serial.tx.find("\"type\":\"sensors\"") != std::string::npos);
    assert(Serial.tx.find("\"firmware\":\"rover-integrated-0.6.0\"") != std::string::npos);
    frame("{\"motor\":\"DC\",\"speed\":30}");
    assert(pwm_pins[MOTOR_PWM_PIN] > 0);
    fake_time += MOTOR_TIMEOUT_MS;
    heartbeat(); loop();
    assert(pwm_pins[MOTOR_PWM_PIN] == 0 && arm.enabled);
    frame("{\"command\":\"STOP_ALL\"}");
    assert(!arm.enabled);
    for (auto& servo : servos) assert(!servo.attached());
    fake_time += 1000; loop();
    assert(logger.rows == 2 && sensors.read_count > 5); // Stop does not stop data collection.
    enable(); assert(arm.enabled);
    const int previous_pulse = servos[0].pulse;
    frame("{\"axis\":\"Axis1\",\"angle\":10}");
    frame("{\"command\":\"STOP_ALL\"}");
    enable();
    assert(servos[0].pulse == previous_pulse); // No queued target jump after stop/re-enable.
    Serial.connected = false; loop();
    assert(!arm.enabled && pwm_pins[MOTOR_PWM_PIN] == 0);
    for (auto& servo : servos) assert(!servo.attached());
    Serial.connected = true; enable();
    fake_time += HEARTBEAT_TIMEOUT_MS; loop();
    assert(!arm.enabled);
    heartbeat(); assert(!arm.enabled);
    enable(); frame("{\"axis\":\"Axis1\",\"angle\":\"bad\"}");
    assert(!arm.enabled);
    enable(); Serial.rx = std::string(600, 'x') + "\n";
    for (int i = 0; i < 5; ++i) readCommands();
    assert(!arm.enabled);
    assert(logger.ready);
    std::cout << "PASS: actual JSON firmware commands, four servo outputs, ramps, motor timeout, live sensor/log schedule, stop, USB loss, no automatic re-enable\n";
}
