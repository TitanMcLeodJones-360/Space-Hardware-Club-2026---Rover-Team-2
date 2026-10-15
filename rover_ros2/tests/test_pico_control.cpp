#include <cassert>
#include <limits>
#include "../pico/rover_pico/control.h"

int main() {
    assert(validatePins());
    if (DRY_RUN) {
        assert(outputConfigurationValid());
    } else {
        assert(outputConfigurationValid() == !USE_SERVOS);
        ArmState hardware;
        hardware.initialize(outputConfigurationValid(), USE_DC_MOTOR);
        hardware.heartbeat(10);
        assert(hardware.enable(10) == !USE_SERVOS);
        if (!USE_SERVOS) {
            assert(!hardware.move(0, 90, 11));
            assert(!hardware.enabled);
            assert(hardware.enable(12));
            assert(hardware.motor(100, 13));
            assert(hardware.motor_speed == MOTOR_MAX_PERCENT);
            assert(hardware.tick(313));
            assert(hardware.motor_speed == 0);
        }
        return 0;
    }
    ArmState arm;
    arm.initialize(true, true);
    assert(!arm.enabled);
    assert(!arm.enable(0));
    arm.heartbeat(100);
    assert(arm.enable(100));
    assert(arm.move(arm.findJoint("Axis1"), 300, 101));
    assert(arm.targets[0] == 180);
    assert(arm.move(0, -10, 102));
    assert(arm.targets[0] == 0);

    assert(arm.motor(100, 110));
    assert(arm.motor_speed == MOTOR_MAX_PERCENT);
    assert(!arm.tick(409));
    assert(arm.tick(410));
    assert(arm.motor_speed == 0 && arm.enabled);
    assert(arm.motor(-15, 500));
    assert(arm.motor_speed == -15);
    arm.stop("Operator stop");
    assert(!arm.enabled && arm.motor_speed == 0);
    assert(arm.motor(0, 501));
    assert(!arm.move(0, 90, 501));
    assert(!arm.enabled);

    arm.heartbeat(600);
    assert(arm.enable(600));
    assert(arm.tick(1600));
    assert(!arm.enabled);
    arm.heartbeat(1601);
    assert(!arm.enabled); // A new heartbeat does not re-enable outputs.
    assert(arm.enable(1601));
    arm.heartbeat(2700); // Late heartbeat before tick() must also stop.
    assert(!arm.enabled);

    assert(arm.enable(2700));
    assert(!arm.motor(std::numeric_limits<float>::quiet_NaN(), 2701));
    assert(!arm.enabled);
    assert(arm.enable(2702));
    assert(!arm.move(-1, 90, 2703));
    assert(!arm.enabled);

    // millis() wraps after about 49 days. Unsigned subtraction stays valid.
    ArmState wrapped;
    wrapped.initialize(true, true);
    wrapped.heartbeat(UINT32_MAX - 100);
    assert(wrapped.enable(UINT32_MAX - 100));
    assert(wrapped.online(50));
    assert(wrapped.motor(15, UINT32_MAX - 50));
    assert(!wrapped.tick(100));
    assert(wrapped.tick(249));
    assert(wrapped.motor_speed == 0 && wrapped.enabled);
    assert(wrapped.tick(899));
    assert(!wrapped.enabled);

    ArmState unavailable;
    unavailable.initialize(false, false);
    unavailable.heartbeat(10);
    assert(!unavailable.enable(10));
    assert(exposedPin(0) && exposedPin(22) && exposedPin(26));
    assert(!exposedPin(-1) && !exposedPin(23) && !exposedPin(29));
}
