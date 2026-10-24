#pragma once
#include <cmath>
#include <cstring>
#include "config.h"

inline bool exposedPin(int pin) {
    return (pin >= 0 && pin <= 22) || (pin >= 26 && pin <= 28);
}

inline bool claimPin(int pin, bool *used) {
    if (!exposedPin(pin) || used[pin]) return false;
    used[pin] = true;
    return true;
}

inline bool validatePins() {
    bool used[29] = {};
    if (!USE_USB_SERIAL && (!claimPin(UART_TX_PIN, used) || !claimPin(UART_RX_PIN, used))) return false;
    if (USE_SENSORS && (!claimPin(I2C_SDA_PIN, used) || !claimPin(I2C_SCL_PIN, used))) return false;
    if (USE_SD && (!claimPin(SD_SCK_PIN, used) || !claimPin(SD_MOSI_PIN, used) ||
                  !claimPin(SD_MISO_PIN, used) || !claimPin(SD_CS_PIN, used))) return false;
    if (!DRY_RUN) {
        for (const auto &joint : JOINTS)
            if (USE_SERVOS && joint.active && !claimPin(joint.pin, used)) return false;
        if (USE_DC_MOTOR && (!claimPin(MOTOR_IN1_PIN, used) || !claimPin(MOTOR_IN2_PIN, used) ||
                            !claimPin(MOTOR_PWM_PIN, used) ||
                            (MOTOR_STBY_PIN >= 0 && !claimPin(MOTOR_STBY_PIN, used)) ||
                            (MOTOR_STBY_PIN < 0 && !MOTOR_STBY_EXTERNALLY_ENABLED))) return false;
    }
    return true;
}

inline bool outputConfigurationValid() {
    if (DRY_RUN) return true;
    bool any_output = USE_DC_MOTOR;
    if (USE_SERVOS && !SERVO_LAYOUT_CONFIRMED) return false;
    if (USE_SERVOS && (!std::isfinite(SERVO_RATE_DEG_S) || SERVO_RATE_DEG_S <= 0 ||
                       SERVO_INTERVAL_MS == 0)) return false;
    if (MOTOR_DIRECTION != 1 && MOTOR_DIRECTION != -1) return false;
    if (USE_DC_MOTOR && (MOTOR_MAX_PERCENT <= 0 || MOTOR_MAX_PERCENT > 100)) return false;
    for (const auto &joint : JOINTS) {
        if (!USE_SERVOS || !joint.active) continue;
        any_output = true;
        if (!(std::isfinite(joint.min_deg) && std::isfinite(joint.max_deg) &&
              std::isfinite(joint.home_deg) && joint.min_deg < joint.max_deg && joint.home_deg >= joint.min_deg &&
              joint.home_deg <= joint.max_deg && joint.min_pulse_us >= 200 &&
              joint.min_pulse_us < joint.max_pulse_us && joint.max_pulse_us <= 3000)) return false;
    }
    return any_output;
}

inline float clampValue(float value, float low, float high) {
    return value < low ? low : (value > high ? high : value);
}

// Dry run uses the same zero-centered limits as the integrated hardware profile.
inline float jointLow(int i) {
    return DRY_RUN && !(JOINTS[i].min_deg < JOINTS[i].max_deg) ? 0.0f : JOINTS[i].min_deg;
}
inline float jointHigh(int i) {
    return DRY_RUN && !(JOINTS[i].min_deg < JOINTS[i].max_deg) ? 180.0f : JOINTS[i].max_deg;
}
inline float jointHome(int i) {
    return DRY_RUN && !(JOINTS[i].min_deg < JOINTS[i].max_deg) ? 90.0f : JOINTS[i].home_deg;
}

// This part doesn't depend on Arduino, so the stop/enable rules can be tested.
struct ArmState {
    bool ready = false;
    bool enabled = false;
    bool heartbeat_seen = false;
    bool motor_ready = false;
    uint32_t last_heartbeat = 0;
    uint32_t last_motor_command = 0;
    float targets[JOINT_COUNT] = {};
    float commanded[JOINT_COUNT] = {}; // Pulse command estimate, not measured position.
    float motor_speed = 0;
    const char *note = "Not configured";

    void initialize(bool configured, bool motor_configured) {
        ready = configured;
        motor_ready = motor_configured;
        for (int i = 0; i < JOINT_COUNT; ++i)
            commanded[i] = targets[i] = jointHome(i);
        note = ready ? "Ready; outputs stopped" : "Finish config.h";
    }

    bool online(uint32_t now) const {
        return heartbeat_seen && uint32_t(now - last_heartbeat) < HEARTBEAT_TIMEOUT_MS;
    }

    void stop(const char *reason) {
        enabled = false;
        motor_speed = 0;
        // Freeze pending ramps. Re-enable resumes the last pulse command rather
        // than advancing toward a target queued before the stop.
        for (int i = 0; i < JOINT_COUNT; ++i) targets[i] = commanded[i];
        note = reason;
    }

    bool stepServos(uint32_t elapsed_ms) {
        if (!enabled) return false;
        // Never catch up with a large jump after a slow SD/sensor operation.
        const float step = SERVO_RATE_DEG_S *
            (elapsed_ms < SERVO_INTERVAL_MS ? elapsed_ms : SERVO_INTERVAL_MS) / 1000.0f;
        bool changed = false;
        for (int i = 0; i < JOINT_COUNT; ++i) {
            const float delta = targets[i] - commanded[i];
            if (delta == 0) continue;
            commanded[i] += clampValue(delta, -step, step);
            changed = true;
        }
        return changed;
    }

    void heartbeat(uint32_t now) {
        if (enabled && !online(now)) stop("Late heartbeat; enable again");
        heartbeat_seen = true;
        last_heartbeat = now;
    }

    bool enable(uint32_t now) {
        if (!ready || !online(now)) {
            stop("Configuration or heartbeat missing");
            return false;
        }
        enabled = true;
        note = "Arm enabled";
        return true;
    }

    int findJoint(const char *name) const {
        for (int i = 0; i < JOINT_COUNT; ++i)
            if (std::strcmp(name, JOINTS[i].name) == 0) return i;
        return -1;
    }

    bool move(int joint, float angle, uint32_t now) {
        if (!enabled || !online(now) || joint < 0 || joint >= JOINT_COUNT ||
            (!DRY_RUN && (!USE_SERVOS || !JOINTS[joint].active)) || !std::isfinite(angle)) {
            stop("Joint command rejected");
            return false;
        }
        const float low = jointLow(joint);
        const float high = jointHigh(joint);
        targets[joint] = clampValue(angle, low, high);
        note = "Joint target updated";
        return true;
    }

    bool motor(float speed, uint32_t now) {
        if (!std::isfinite(speed) || speed < -100 || speed > 100) {
            stop("Invalid motor speed");
            return false;
        }
        if (speed == 0) {
            motor_speed = 0;
            note = "DC motor stopped";
            return true;
        }
        if (!enabled || !online(now) || !motor_ready) {
            stop("Motor command rejected");
            return false;
        }
        motor_speed = clampValue(speed, -MOTOR_MAX_PERCENT, MOTOR_MAX_PERCENT);
        last_motor_command = now;
        note = "DC motor running; release button to stop";
        return true;
    }

    bool tick(uint32_t now) {
        if (enabled && !online(now)) {
            stop("Ground station heartbeat timed out");
            return true;
        }
        if (motor_speed != 0 && uint32_t(now - last_motor_command) >= MOTOR_TIMEOUT_MS) {
            motor_speed = 0;
            note = "DC motor command timed out";
            return true;
        }
        return false;
    }
};
