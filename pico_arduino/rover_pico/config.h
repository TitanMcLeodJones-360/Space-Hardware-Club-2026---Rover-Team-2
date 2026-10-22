#pragma once
#include <stdint.h>

// From the authoritative two-month-electrical-schematic.svg supplied 21 October 2026.
// GPIO numbers below are NOT physical header pin numbers.
// Real sensors + SD run by default. Actuator signals stay off in DRY_RUN.
#ifndef ROVER_DRY_RUN
#define ROVER_DRY_RUN 1
#endif
#ifndef ROVER_USE_SERVOS
#define ROVER_USE_SERVOS 0
#endif
constexpr bool DRY_RUN = ROVER_DRY_RUN;
constexpr bool USE_SERVOS = ROVER_USE_SERVOS;
constexpr bool SERVO_LAYOUT_CONFIRMED = false;
constexpr bool USE_USB_SERIAL = true;
constexpr int UART_TX_PIN = -1;
constexpr int UART_RX_PIN = -1;
constexpr uint32_t BAUDRATE = 115200;
constexpr uint32_t HEARTBEAT_TIMEOUT_MS = 1000;
constexpr uint32_t MOTOR_TIMEOUT_MS = 300;
constexpr uint32_t SENSOR_INTERVAL_MS = 200;
constexpr uint32_t LOG_INTERVAL_MS = 1000;

struct JointConfig {
    const char *name;
    bool active;
    int pin;
    float min_deg, max_deg, home_deg;
    int min_pulse_us, max_pulse_us;
    bool reversed;
};

// Keep electrical axis names until Mechanical confirms joint mapping.
// Axis3A angular range is team-reported; centered 0 still needs PWM calibration.
// Axis3B: reported 120 total / 50 needed; direction/zero still unconfirmed.
// AXIS_3-1 and AXIS_3-2 may be coupled: do not assume independent joints.
// Replace -1 calibration values with measured limits before USE_SERVOS=true.
constexpr JointConfig JOINTS[] = {
    {"Axis1",  true, 15, -1, -1, -1, -1, -1, false}, // M1: AXIS_1_PWM
    {"Axis2",  true, 14, -1, -1, -1, -1, -1, false}, // M2: AXIS_2_PWM
    {"Axis3A", true, 13, -70, 70, 0, -1, -1, false}, // M3: AXIS_3-1_PWM
    {"Axis3B", true, 12, -1, -1, -1, -1, -1, false}, // M4: AXIS_3-2_PWM
};
constexpr int JOINT_COUNT = sizeof(JOINTS) / sizeof(JOINTS[0]);

constexpr bool USE_SENSORS = true;
constexpr int I2C_SDA_PIN = 4; // Physical header pin 6; Wire (I2C0).
constexpr int I2C_SCL_PIN = 5; // Physical header pin 7.
constexpr uint8_t BNO055_ADDRESS = 0x28;
constexpr uint8_t BMP388_ADDRESS = 0x77;
constexpr float SEA_LEVEL_PRESSURE_HPA = 1013.25f; // Update for test location.

constexpr bool USE_SD = true;
constexpr int SD_SCK_PIN = 18;
constexpr int SD_MOSI_PIN = 19; // SD SI
constexpr int SD_MISO_PIN = 16; // SD SO
constexpr int SD_CS_PIN = 17;

// Axis 0 uses TB6612 channel A. No encoder/position feedback is shown.
constexpr bool USE_DC_MOTOR = true;
constexpr int MOTOR_IN1_PIN = 8; // Physical header pin 11.
constexpr int MOTOR_IN2_PIN = 7; // Physical header pin 10.
constexpr int MOTOR_PWM_PIN = 6; // Physical header pin 9.
constexpr int MOTOR_STBY_PIN = -1; // Unwired in supplied schematic.
// Valid for the specified Adafruit TB6612 board's onboard STBY pull-up.
// For a board without that pull-up, wire STBY and set this false.
constexpr bool MOTOR_STBY_EXTERNALLY_ENABLED = true;
constexpr int MOTOR_DIRECTION = 1; // Change to -1 after checking direction.
constexpr float MOTOR_MAX_PERCENT = 30.0f; // Bench duty limit, not measured speed.
