#include <cassert>
#include <limits>
#include <iostream>
#include "../pico/rover_pico/control.h"

int main() {
    assert(validatePins() && outputConfigurationValid());
    ArmState arm;
    arm.initialize(true, true);
    assert(!arm.enabled && !arm.enable(0));
    for (int i = 0; i < JOINT_COUNT; ++i) {
        assert(arm.targets[i] == 0 && arm.commanded[i] == 0);
        assert(jointLow(i) == -10 && jointHigh(i) == 10);
    }
    arm.heartbeat(100);
    assert(arm.enable(100));
    if (DRY_RUN || USE_SERVOS) {
        for (int i = 0; i < JOINT_COUNT; ++i) {
            assert(arm.move(i, 30, 101));
            assert(arm.targets[i] == 10 && arm.commanded[i] == 0);
        }
        assert(arm.stepServos(20));
        assert(std::fabs(arm.commanded[0] - 0.1f) < 0.0001f);
        assert(arm.stepServos(10000)); // No catch-up jump after a delayed loop.
        assert(std::fabs(arm.commanded[0] - 0.2f) < 0.0001f);
        arm.stop("Operator stop");
        assert(!arm.enabled && !arm.stepServos(20));
        for (int i = 0; i < JOINT_COUNT; ++i) assert(arm.targets[i] == arm.commanded[i]);
        assert(arm.enable(102));
        assert(!arm.stepServos(20)); // Do not resume a pre-stop destination.
        assert(arm.move(0, -30, 103));
        assert(arm.targets[0] == -10);
    } else {
        assert(!arm.move(0, 1, 101));
        assert(!arm.enabled);
        assert(arm.enable(102));
    }
    assert(arm.motor(100, 110));
    assert(arm.motor_speed == MOTOR_MAX_PERCENT);
    assert(!arm.tick(409));
    assert(arm.tick(410));
    assert(arm.motor_speed == 0 && arm.enabled);
    assert(arm.motor(-15, 500));
    arm.stop("Stop");
    assert(!arm.enabled && arm.motor_speed == 0);
    assert(arm.motor(0, 501));
    arm.heartbeat(600);
    assert(!arm.enabled && arm.enable(600));
    assert(arm.tick(1600) && !arm.enabled);
    arm.heartbeat(1601);
    assert(!arm.enabled);
    assert(arm.enable(1601));
    arm.heartbeat(2700);
    assert(!arm.enabled);
    assert(arm.enable(2700));
    assert(!arm.motor(std::numeric_limits<float>::quiet_NaN(), 2701));
    assert(!arm.enabled);
    assert(arm.enable(2702));
    assert(!arm.move(-1, 0, 2703));
    assert(!arm.enabled);

    ArmState wrapped;
    wrapped.initialize(true, true);
    wrapped.heartbeat(UINT32_MAX - 100);
    assert(wrapped.enable(UINT32_MAX - 100) && wrapped.online(50));
    assert(wrapped.motor(15, UINT32_MAX - 50));
    assert(!wrapped.tick(100) && wrapped.tick(249));
    assert(wrapped.motor_speed == 0 && wrapped.enabled);
    assert(wrapped.tick(899) && !wrapped.enabled);
    ArmState unavailable;
    unavailable.initialize(false, false);
    unavailable.heartbeat(10);
    assert(!unavailable.enable(10));
    bool pins[29] = {};
    assert(claimPin(15, pins) && !claimPin(15, pins));
    assert(!exposedPin(-1) && !exposedPin(23) && !exposedPin(29));
    std::cout << "PASS: integrated control profile and stop/ramp/timeout rules\n";
}
