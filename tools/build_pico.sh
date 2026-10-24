#!/usr/bin/env bash
set -eo pipefail
rover_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
arduino-cli config add board_manager.additional_urls \
    https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json
arduino-cli core update-index
arduino-cli core install rp2040:rp2040@6.3.0
arduino-cli lib install ArduinoJson@7.4.2 'Adafruit BNO055@1.6.4' 'Adafruit BMP3XX Library@2.1.6' \
    'Adafruit BusIO@1.17.4' 'Adafruit Unified Sensor@1.1.15'
rover_build=$(mktemp -d)
trap 'rm -rf -- "$rover_build"' EXIT
arduino-cli compile --fqbn rp2040:rp2040:rpipico:freq=125 \
    --output-dir "$rover_build" "$rover_repo/pico_arduino/rover_pico"
mkdir -p -- "$rover_repo/firmware"
cp -- "$rover_build/rover_pico.ino.uf2" "$rover_repo/firmware/Pico_RP2040_Integrated.uf2"
echo "Built $rover_repo/firmware/Pico_RP2040_Integrated.uf2"
