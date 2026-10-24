#pragma once
#include <stdint.h>

// From the authoritative two-month-electrical-schematic.svg supplied 21 October 2026.
// GPIO numbers below are NOT physical header pin numbers.
// Integrated hardware profile: sensors, SD, four servos and TB6612 motor.
// Outputs stay off until a fresh heartbeat and an explicit ARM_ENABLE.
#ifndef ROVER_DRY_RUN
#define ROVER_DRY_RUN 0
#endif
#ifndef ROVER_USE_SERVOS
#define ROVER_USE_SERVOS 1
#endif
constexpr bool DRY_RUN = ROVER_DRY_RUN;
constexpr bool USE_SERVOS = ROVER_USE_SERVOS;
// The user authorized the corrected schematic's four channels and assumed zero pose.
constexpr bool SERVO_LAYOUT_CONFIRMED = true;
constexpr bool USE_USB_SERIAL = true;
constexpr int UART_TX_PIN = -1;
constexpr int UART_RX_PIN = -1;
constexpr uint32_t BAUDRATE = 115200;
constexpr uint32_t HEARTBEAT_TIMEOUT_MS = 1000;
constexpr uint32_t MOTOR_TIMEOUT_MS = 300;
constexpr uint32_t SENSOR_INTERVAL_MS = 200;
constexpr uint32_t LOG_INTERVAL_MS = 1000;
constexpr uint32_t SERVO_INTERVAL_MS = 20;
constexpr float SERVO_RATE_DEG_S = 5.0f;

struct JointConfig {
    const char *name;
    bool active;
    int pin;
    float min_deg, max_deg, home_deg;
    int min_pulse_us, max_pulse_us;
    bool reversed;
};

// Provisional zero-centered commissioning limits for the mounted arm.
// Assumption authorized by the user: all four joints are at 0 degrees.
// Electrically, 0 maps to 1500 us; +/-10 maps to 1400/1600 us.
// 10 us/degree is a provisional mapping, not measured joint feedback/calibration.
// These bounds are NOT verified mechanical travel limits. Expand each joint's
// limits and pulse mapping only after checking direction, zero and clearance.
// The earlier Axis3A +/-70 mechanical report does not establish servo PWM endpoints.
constexpr JointConfig JOINTS[] = {
    {"Axis1",  true, 15, -10, 10, 0, 1400, 1600, false}, // M1: AXIS_1_PWM
    {"Axis2",  true, 14, -10, 10, 0, 1400, 1600, false}, // M2: AXIS_2_PWM
    {"Axis3A", true, 13, -10, 10, 0, 1400, 1600, false}, // M3: AXIS_3-1_PWM
    {"Axis3B", true, 12, -10, 10, 0, 1400, 1600, false}, // M4: AXIS_3-2_PWM
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
