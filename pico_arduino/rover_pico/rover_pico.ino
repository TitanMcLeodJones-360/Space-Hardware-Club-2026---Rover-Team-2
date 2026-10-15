#include <Arduino.h>
#include <ArduinoJson.h>
#include <Servo.h>
#include "config.h"
#include "control.h"
#include "sensors.h"
#include "sd_logger.h"

ArmState arm;
Servo servos[JOINT_COUNT];
Sensors sensors;
SDLogger logger;
SensorData readings;
bool pins_ok = false;
bool motor_pins_ready = false;
bool uart_started = false;
uint32_t started, last_sensor, last_log, last_status;
char command_buffer[512];
size_t command_length = 0;
bool discard_line = false;
const char *setup_error = "";

Stream &link() {
    if (USE_USB_SERIAL || !uart_started) return Serial;
    return Serial1;
}

bool configureOutputs() {
    if (!pins_ok) return false;
    if (DRY_RUN) return true;
    if (!outputConfigurationValid()) return false;
    if (USE_DC_MOTOR) {
        if (MOTOR_STBY_PIN >= 0) {
            digitalWrite(MOTOR_STBY_PIN, LOW);
            pinMode(MOTOR_STBY_PIN, OUTPUT);
        }
        digitalWrite(MOTOR_IN1_PIN, LOW);
        digitalWrite(MOTOR_IN2_PIN, LOW);
        digitalWrite(MOTOR_PWM_PIN, LOW);
        pinMode(MOTOR_IN1_PIN, OUTPUT);
        pinMode(MOTOR_IN2_PIN, OUTPUT);
        pinMode(MOTOR_PWM_PIN, OUTPUT);
        digitalWrite(MOTOR_IN1_PIN, LOW);
        digitalWrite(MOTOR_IN2_PIN, LOW);
        analogWriteFreq(20000);
        analogWriteRange(255);
        analogWrite(MOTOR_PWM_PIN, 0);
        motor_pins_ready = true;
    }
    return true;
}

void applyMotor() {
    if (DRY_RUN || !motor_pins_ready) return;
    // Remove PWM before changing direction.
    analogWrite(MOTOR_PWM_PIN, 0);
    digitalWrite(MOTOR_IN1_PIN, arm.enabled && arm.motor_speed * MOTOR_DIRECTION > 0 ? HIGH : LOW);
    digitalWrite(MOTOR_IN2_PIN, arm.enabled && arm.motor_speed * MOTOR_DIRECTION < 0 ? HIGH : LOW);
    if (MOTOR_STBY_PIN >= 0)
        digitalWrite(MOTOR_STBY_PIN, arm.enabled && arm.motor_speed != 0 ? HIGH : LOW);
    if (arm.enabled) analogWrite(MOTOR_PWM_PIN, int(std::fabs(arm.motor_speed) * 255 / 100));
}

void stopOutputs() {
    for (auto &servo : servos) if (servo.attached()) servo.detach();
    applyMotor();
}

void stopAll(const char *reason) {
    arm.stop(reason);
    stopOutputs();
}

int servoPulse(int index) {
    const auto &joint = JOINTS[index];
    float fraction = (arm.targets[index] - joint.min_deg) / (joint.max_deg - joint.min_deg);
    if (joint.reversed) fraction = 1.0f - fraction;
    return int(joint.min_pulse_us + fraction *
               (joint.max_pulse_us - joint.min_pulse_us));
}

void applyServo(int index) {
    if (DRY_RUN || !USE_SERVOS || !JOINTS[index].active) return;
    servos[index].writeMicroseconds(servoPulse(index));
}

bool attachServos() {
    if (DRY_RUN || !USE_SERVOS) return true;
    for (int i = 0; i < JOINT_COUNT; ++i) {
        if (!JOINTS[i].active || servos[i].attached()) continue;
        // Supply the first target pulse explicitly, avoiding a default center pulse.
        servos[i].attach(JOINTS[i].pin, JOINTS[i].min_pulse_us,
                         JOINTS[i].max_pulse_us, servoPulse(i));
        if (!servos[i].attached()) {
            stopAll("Servo attach failed");
            return false;
        }
        applyServo(i);
    }
    return true;
}

void sendStatus(bool force) {
    const uint32_t now = millis();
    // Heartbeats and held motor buttons should not flood a UART link.
    if (!force && uint32_t(now - last_status) < 250) return;
    if (USE_USB_SERIAL && !Serial) return;
    last_status = now;
    JsonDocument doc;
    doc["type"] = "status";
    doc["mode"] = DRY_RUN ? "simulation" : "hardware";
    doc["ready"] = arm.ready;
    doc["enabled"] = arm.enabled;
    doc["note"] = arm.note;
    if (*setup_error) doc["error"] = setup_error;
    JsonObject targets = doc["targets"].to<JsonObject>();
    JsonObject limits = doc["limits"].to<JsonObject>();
    for (int i = 0; i < JOINT_COUNT; ++i) {
        if (!DRY_RUN && (!USE_SERVOS || !JOINTS[i].active)) continue;
        const char *name = JOINTS[i].name;
        targets[name] = arm.targets[i];
        JsonArray range = limits[name].to<JsonArray>();
        range.add(DRY_RUN ? 0.0f : JOINTS[i].min_deg);
        range.add(DRY_RUN ? 180.0f : JOINTS[i].max_deg);
    }
    doc["motor_ready"] = arm.motor_ready;
    doc["motor_speed"] = arm.motor_speed;
    doc["motor_limit"] = MOTOR_MAX_PERCENT;
    doc["imu_ready"] = sensors.imu_ready;
    doc["bmp_ready"] = sensors.bmp_ready;
    doc["sd_ready"] = logger.ready;
    doc["sd_rows"] = logger.rows;
    doc["sd_file"] = logger.filename;
    doc["sensor_error"] = sensors.error;
    doc["sd_error"] = logger.error;
    serializeJson(doc, link());
    link().println();
}

void putReading(JsonObject data, const char *name, float value) {
    if (std::isfinite(value)) data[name] = value;
    else data[name] = nullptr;
}

void sendSensors() {
    if (USE_USB_SERIAL && !Serial) return;
    JsonDocument doc;
    doc["type"] = "sensors";
    doc["mode"] = "hardware"; // These are real readings, even during output dry run.
    doc["elapsed_ms"] = uint32_t(millis() - started);
    JsonObject data = doc["data"].to<JsonObject>();
    putReading(data, "temperature", readings.temperature);
    putReading(data, "pressure", readings.pressure);
    putReading(data, "accel_x", readings.accel_x);
    putReading(data, "accel_y", readings.accel_y);
    putReading(data, "accel_z", readings.accel_z);
    putReading(data, "altitude", readings.altitude);
    serializeJson(doc, link());
    link().println();
}

bool numeric(JsonVariantConst value) {
    return !value.is<bool>() && value.is<float>() && std::isfinite(value.as<float>());
}

void handleCommand(const char *line) {
    JsonDocument doc;
    if (deserializeJson(doc, line) || !doc.is<JsonObject>()) {
        stopAll("Invalid JSON command");
        sendStatus(false);
        return;
    }
    const uint32_t now = millis();
    if (doc["command"].is<const char *>() && doc.size() == 1) {
        const char *command = doc["command"].as<const char *>();
        if (std::strcmp(command, "HEARTBEAT") == 0) arm.heartbeat(now);
        else if (std::strcmp(command, "STOP_ALL") == 0) stopAll("Stopped by operator");
        else if (std::strcmp(command, "LINK_LOST") == 0) stopAll("Connection lost");
        else if (std::strcmp(command, "ARM_ENABLE") == 0) {
            if (arm.enable(now)) attachServos();
        } else if (std::strcmp(command, "STATUS") != 0) stopAll("Unknown control command");
    } else if (doc.size() == 2 && doc["axis"].is<const char *>() && numeric(doc["angle"])) {
        if (arm.move(arm.findJoint(doc["axis"].as<const char *>()), doc["angle"].as<float>(), now))
            applyServo(arm.findJoint(doc["axis"].as<const char *>()));
    } else if (doc.size() == 2 && doc["motor"].is<const char *>() &&
               std::strcmp(doc["motor"].as<const char *>(), "DC") == 0 && numeric(doc["speed"])) {
        arm.motor(doc["speed"].as<float>(), now);
    } else stopAll("Invalid command fields");
    if (!arm.enabled) stopOutputs();
    else applyMotor();
    sendStatus(false);
}

void readCommands() {
    int budget = 128;
    while (budget-- > 0 && link().available()) {
        const char ch = char(link().read());
        if (ch == '\n') {
            if (!discard_line && command_length > 0) {
                command_buffer[command_length] = '\0';
                handleCommand(command_buffer);
            }
            command_length = 0;
            discard_line = false;
        } else if (ch != '\r' && !discard_line) {
            if (ch == '\0' || command_length >= sizeof(command_buffer) - 1) {
                discard_line = true;
                command_length = 0;
                stopAll("Command line too long or invalid");
                sendStatus(false);
            } else command_buffer[command_length++] = ch;
        }
    }
}

void setup() {
    Serial.begin(BAUDRATE);
    pins_ok = validatePins();
    if (!pins_ok) setup_error = "Invalid or repeated GPIO pins; check config.h";
    if (!USE_USB_SERIAL && pins_ok) {
        if (!Serial1.setTX(UART_TX_PIN) || !Serial1.setRX(UART_RX_PIN)) {
            pins_ok = false;
            setup_error = "Invalid UART0 pin selection";
        } else {
            Serial1.setFIFOSize(1024);
            Serial1.begin(BAUDRATE);
            uart_started = true;
        }
    }
    const bool outputs_ready = configureOutputs();
    arm.initialize(outputs_ready, outputs_ready && (DRY_RUN || USE_DC_MOTOR));
    if (!outputs_ready && !*setup_error) setup_error = "Finish servo and motor settings in config.h";
    if (pins_ok) {
        sensors.begin();
        logger.begin();
    }
    started = last_sensor = last_log = last_status = millis();
    sendStatus(true);
}

void loop() {
    if (arm.tick(millis())) {
        if (!arm.enabled) stopOutputs();
        else applyMotor();
        sendStatus(false);
    }
    readCommands();
    const uint32_t now = millis();
    if (pins_ok && USE_SENSORS && uint32_t(now - last_sensor) >= SENSOR_INTERVAL_MS) {
        last_sensor = now;
        readings = sensors.read();
        sendSensors();
    }
    if (pins_ok && USE_SD && uint32_t(now - last_log) >= LOG_INTERVAL_MS) {
        last_log = now;
        logger.write(uint32_t(now - started), readings);
    }
    if (uint32_t(now - last_status) >= 250) {
        sendStatus(false);
    }
}
