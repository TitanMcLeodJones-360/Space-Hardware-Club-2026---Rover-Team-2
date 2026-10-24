# Rover Team 2 — Setup and Operation

Set up the ground station on your own PC, connect to the Orange Pi, and test the Pico's sensors and actuator commands.

**New PC:** [installation](#installation). **Already set up:** [daily startup](#daily-startup). **No rover:** [local simulation](#local-simulation-without-the-rover).

## What runs where

| Device | Software | Connection |
| --- | --- | --- |
| Laptop, Ubuntu 24.04 in WSL 2 | PyQt ground station, ROS 2 Jazzy | Ethernet to Orange Pi |
| Orange Pi Zero 3, club Armbian/Ubuntu Noble image | ROS 2 arm bridge | Ethernet to laptop; USB to Pico |
| RP2040 Raspberry Pi Pico | Arduino C++ firmware | Servos, TB6612, BNO055, BMP388, SD breakout |

The GUI sends commands and a heartbeat. The Pi translates commands into newline-delimited JSON for the Pico and publishes its replies as ROS messages. Start the bridge on the Pi and the GUI on the laptop. Connecting hardware does not open the GUI automatically.

Use one ground station and one bridge during a test. Sensors can run while actuators are disabled.

| Terminal label | Example prompt | Used for |
| --- | --- | --- |
| **Windows PowerShell** | `PS C:\Users\yourname>` | WSL setup, SSH/SCP, Windows firewall |
| **Laptop Ubuntu/WSL** | `yourname@your-laptop:~$` | Installing/building ROS packages and the GUI |
| **Orange Pi SSH** | `rover2@orangepizero3:~$` | Pico USB checks and hardware bridge |

Run `source`, `export` and `apt` in Linux, not PowerShell. Copy commands without prompts. PowerShell commands below support Windows PowerShell 5.

## Matching code and firmware

Repository: [Space Hardware Club — Rover Team 2](https://github.com/TitanMcLeodJones-360/Space-Hardware-Club-2026---Rover-Team-2/tree/rover-software)
Branch: **`rover-software`**
Complete package: **`Rover_Complete.zip`**
ROS application: **0.6.1**
Pico firmware: **`rover-integrated-0.6.0`**

This package contains the complete GUI, two ROS packages, Arduino C++ firmware,
compiled UF2, corrected schematic, tests and build tools. The 0.6.1 host release
adds bounded serial framing and accepts the first complete reply. The firmware
source and UF2 are the same integrated 0.6.0 build; their unchanged version is intentional.
The GUI uses mouse/keyboard controls. Xbox integration is removed.

The package was prepared against GitHub commit `7822470`. Publish the complete
release using the ZIP's `Commit-To-Git.ps1`, then new teammates can clone it.
Before that commit reaches GitHub, an older clone needs the ZIP applied in step 3.

Use `firmware/Pico_RP2040_Integrated.uf2` for the original **RP2040 Pico**.
It runs sensors, SD, four servo channels and the DC motor. Older Bench/Schematic/Xbox
UF2 images are superseded and removed by the updater. This image is not for Pico 2.

**Hardware progress:** real Pico status, temperature, pressure and estimated
altitude previously reached the Pi; laptop status was also received. SD mounting
failed and acceleration reported three zeros at the last supplied check.
Physical servo/DC movement, travel calibration, SD logging and sensor accuracy
still require verification. Software readiness does not establish those results.

## Installation

Run one block at a time. If a command fails, resolve that error before continuing with the next block.

### 1. Install Ubuntu 24.04 in WSL 2

**Windows PowerShell — Run as Administrator**

```powershell
wsl --install -d Ubuntu-24.04
```

Restart Windows if requested. Open Ubuntu 24.04 and create a Linux username/password.

If WSL is already installed:

```powershell
wsl --update
wsl --list --verbose
```

Ubuntu 24.04 must show version **2**. If it shows 1:

```powershell
wsl --set-version Ubuntu-24.04 2
```

This guide's direct-Ethernet configuration uses **Windows 11 22H2 or newer** with mirrored WSL networking. Open the configuration file:

```powershell
notepad "$env:USERPROFILE\.wslconfig"
```

Create or edit its existing `[wsl2]` section:

```ini
[wsl2]
networkingMode=mirrored
firewall=true
```

Preserve other settings; do not duplicate the section. Save the file. Close running WSL jobs before applying it:

```powershell
wsl --shutdown
wsl -d Ubuntu-24.04
```

WSLg displays the Linux GUI on Windows. A separate X server or manually changed `DISPLAY` is not normally needed.

**Native Ubuntu 24.04:** skip WSL/Windows-specific steps and use the Linux commands with your actual network addresses.

### 2. Install ROS 2 Jazzy and dependencies

**Laptop Ubuntu/WSL**

Confirm Ubuntu 24.04:

```bash
. /etc/os-release
printf '%s\n' "$PRETTY_NAME"
```

If `/opt/ros/jazzy/setup.bash` exists, skip the ROS repository/installation block and install the dependencies below it.

On a fresh Ubuntu 24.04 installation:

```bash
sudo apt update
sudo apt install -y locales software-properties-common curl git python3
sudo locale-gen en_US.UTF-8
sudo update-locale LANG=en_US.UTF-8
export LANG=en_US.UTF-8
sudo add-apt-repository -y universe

rover_apt_version=$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')
rover_ubuntu_codename=$(. /etc/os-release; printf '%s' "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
curl -fL -o /tmp/rover-ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${rover_apt_version}/ros2-apt-source_${rover_apt_version}.${rover_ubuntu_codename}_all.deb"
sudo dpkg -i /tmp/rover-ros2-apt-source.deb

sudo apt update
sudo apt upgrade -y
sudo apt install -y ros-jazzy-ros-base ros-jazzy-rmw-fastrtps-cpp
```

Install build tools and GUI/runtime dependencies:

```bash
sudo apt update
sudo apt install -y git python3-colcon-common-extensions python3-rosdep ros-jazzy-rmw-fastrtps-cpp \
  python3-pyqt5 python3-pyqtgraph python3-serial

source /opt/ros/jazzy/setup.bash
ros2 --help
```

The club Pi image already has Jazzy. A new teammate's laptop does not require re-imaging the shared Pi.

### 3. Clone the complete release

**Laptop Ubuntu/WSL**

Use a workspace in your Linux home folder:

```bash
mkdir -p ~/rover_ws/src
git clone --single-branch --branch rover-software \
  https://github.com/TitanMcLeodJones-360/Space-Hardware-Club-2026---Rover-Team-2.git \
  ~/rover_ws/src/rover_team
```

If that checkout exists, skip cloning and inspect
`git -C ~/rover_ws/src/rover_team status -sb`. Preserve existing work.
After the lead publishes release 0.6.1, the clone contains the complete code.
Check the required files:

```bash
test -f ~/rover_ws/src/rover_team/rover_ros2/rover_control/serial_framing.py
test -f ~/rover_ws/src/rover_team/firmware/Pico_RP2040_Integrated.uf2
```

If this is an older clone, download **Rover_Complete.zip** into Windows Downloads,
then apply it without pulling over local edits:

```bash
read -r -p 'Windows user folder name, as shown under C:\Users: ' rover_windows_user
rover_update_zip="/mnt/c/Users/$rover_windows_user/Downloads/Rover_Complete.zip"
python3 -m zipfile -e "$rover_update_zip" ~/rover_complete_release
python3 ~/rover_complete_release/apply_update.py ~/rover_ws/src/rover_team
```

The updater backs up replaced/removed files under `~/rover_ws/src/Rover_Complete_Backups/`.
It installs the complete release without committing/pushing and preserves unrelated
files and ignore rules. It replaces release-managed source files, so coordinate
before applying over a teammate's uncommitted changes. A teammate does not need
push access to clone this public repository.

### 4. Build the laptop workspace

**Laptop Ubuntu/WSL**

Initialize rosdep once; skip initialization if already done:

```bash
sudo rosdep init
rosdep update
```

Install declared dependencies and build:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/rover_ws

rosdep install --from-paths src/rover_team/rover_interfaces src/rover_team/rover_ros2 \
  --ignore-src --rosdistro jazzy -r -y

colcon build --symlink-install \
  --base-paths src/rover_team/rover_interfaces src/rover_team/rover_ros2 \
  --packages-up-to rover_control

source ~/rover_ws/install/setup.bash
ros2 interface show rover_interfaces/msg/ArmStatus
```

Expected: **2 packages finished**, `rover_interfaces` and `rover_control`. Resolve build errors first. Build separately on each machine; do not copy laptop `build/` or `install/` directories onto the ARM Pi.

## Ethernet and ROS network setup

### 5. Find the current IP addresses

Connect Ethernet between laptop and Pi. To share Wi-Fi internet, open `ncpa.cpl` on Windows. In Wi-Fi **Properties → Sharing**, enable Internet Connection Sharing and select the Ethernet adapter connected to the Pi.

**Windows PowerShell**

```powershell
Get-NetAdapter | Format-Table Name, Status, LinkSpeed
Get-NetIPAddress -InterfaceAlias "Ethernet" -AddressFamily IPv4 |
    Format-Table IPAddress, PrefixLength
```

Substitute the actual adapter name if it is not `Ethernet`. The tested laptop Ethernet/ICS address is **192.168.137.1/24**.

On a Pi console or existing SSH session:

**Orange Pi**

```bash
ip -br -4 addr
```

Use the IPv4 beside **end0**. If missing:

```bash
sudo networkctl renew end0
```

Wait a few seconds and check again. This image uses systemd-networkd; `nmcli` is not installed.

| Last reported IP | Meaning |
| --- | --- |
| `192.168.137.1` | Laptop Ethernet/ICS |
| `192.168.137.218` | Pi Ethernet; verify after reconnecting |
| `10.86.173.207` | Pi Wi-Fi; campus Wi-Fi may restrict ROS traffic |

The Pi gets DHCP addresses. Replace `192.168.137.218` in commands/settings if `end0` changes. Use the direct Ethernet address, not the WAN/public address from the login banner.

**Windows PowerShell**

```powershell
ssh rover2@192.168.137.218
```

Use the Pi account password from the lead. Success shows `rover2@orangepizero3`.

If DHCP is missing, this team's Pi has a known Ethernet link-local address:

```powershell
$roverEthIndex = (Get-NetAdapter -Name "Ethernet").ifIndex
ssh "rover2@fe80::c7ff:fec0:cfa1%$roverEthIndex"
```

This IPv6 address is specific to this Orange Pi. Once logged in, renew/check `end0`. IPv6 SSH alone does not establish this guide's IPv4 ROS connection.

### 6. Save settings on both computers

Create these files once using the actual step-5 addresses. Edit an existing file rather than overwriting unrelated settings.

**Laptop Ubuntu/WSL**

```bash
mkdir -p ~/.config/rover
cat > ~/.config/rover/pc.env <<'EOF'
source /opt/ros/jazzy/setup.bash
source "$HOME/rover_ws/install/setup.bash"
unset ROS_LOCALHOST_ONLY
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=2
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROVER_PI_IP=192.168.137.218
export ROS_STATIC_PEERS="$ROVER_PI_IP"
EOF
```

**Orange Pi SSH**

```bash
mkdir -p ~/.config/rover
cat > ~/.config/rover/pi.env <<'EOF'
source /opt/ros/jazzy/setup.bash
source "$HOME/rover_ws/install/setup.bash"
unset ROS_LOCALHOST_ONLY
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=2
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_STATIC_PEERS=192.168.137.1
EOF
```

Laptop peer = Pi. Pi peer = laptop. Both use domain **2** and **Fast DDS**. `LOCALHOST` plus static peers permits discovery on the specified remote machine without relying on subnet multicast.

Processes read settings at startup. Restart the affected GUI/bridge after changing an address.

### 7. Allow ROS UDP through Windows and WSL

Ping/SSH can work while ROS UDP is blocked. The tested setup needed both Windows and WSL Hyper-V inbound rules.

**Windows PowerShell — Run as Administrator**

Enter the current **Pi Ethernet IPv4** when prompted. This creates/updates rules restricted to that address and domain-2 UDP ports **7900–8149**, covering the normal participant range.

```powershell
$roverPiIP = Read-Host "Orange Pi Ethernet IPv4 from end0"

if (Get-NetFirewallRule -Name "RoverROS2-Host" -ErrorAction SilentlyContinue) {
    Get-NetFirewallRule -Name "RoverROS2-Host" |
        Get-NetFirewallAddressFilter |
        Set-NetFirewallAddressFilter -RemoteAddress $roverPiIP
} else {
    New-NetFirewallRule -Name "RoverROS2-Host" `
        -DisplayName "Rover ROS2 from Orange Pi" `
        -Direction Inbound -Action Allow -Protocol UDP `
        -LocalPort 7900-8149 -RemoteAddress $roverPiIP -Profile Any
}

if (Get-NetFirewallHyperVRule -Name "RoverROS2-WSL" -ErrorAction SilentlyContinue) {
    Set-NetFirewallHyperVRule -Name "RoverROS2-WSL" `
        -RemoteAddresses $roverPiIP
} else {
    New-NetFirewallHyperVRule -Name "RoverROS2-WSL" `
        -DisplayName "Rover ROS2 into WSL" `
        -Direction Inbound -Action Allow -Protocol UDP `
        -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' `
        -LocalPorts "7900-8149" -RemoteAddresses $roverPiIP
}
```

**Access is denied:** reopen PowerShell as Administrator. Missing Hyper-V cmdlets: check Windows/WSL compatibility. Keep the firewall enabled.

On native Ubuntu or a Pi with UFW enabled, check `sudo ufw status`. Any needed rule should also restrict access to the other machine's IP and required UDP range.

## Prepare the Orange Pi and Pico

### 8. Install matching Pi source

Skip this if the lead already prepared/built the Pi. Adding a teammate's laptop does not require reflashing the rover.

For a new Pi checkout, install step 2's build/runtime dependencies with Jazzy already present, then:

**Orange Pi SSH**

```bash
mkdir -p ~/rover_ws/src
git clone --single-branch --branch rover-software \
  https://github.com/TitanMcLeodJones-360/Space-Hardware-Club-2026---Rover-Team-2.git \
  ~/rover_ws/src/rover_team
```

Skip cloning if the checkout exists. Transfer the complete ZIP:

**Windows PowerShell**

```powershell
$roverPiIP = Read-Host "Orange Pi Ethernet IPv4 from end0"
scp "$env:USERPROFILE\Downloads\Rover_Complete.zip" "rover2@${roverPiIP}:/home/rover2/Rover_Complete.zip"
```

Stop any existing bridge with Ctrl+C in its terminal before updating.

**Orange Pi SSH**

```bash
python3 -m zipfile -e ~/Rover_Complete.zip ~/rover_complete_release
python3 ~/rover_complete_release/apply_update.py ~/rover_ws/src/rover_team

source /opt/ros/jazzy/setup.bash
cd ~/rover_ws
rosdep install --from-paths src/rover_team/rover_interfaces src/rover_team/rover_ros2 \
  --ignore-src --rosdistro jazzy -r -y

colcon build --symlink-install \
  --base-paths src/rover_team/rover_interfaces src/rover_team/rover_ros2 \
  --packages-up-to rover_control
```

Initialize/update rosdep as in step 4 if needed. Use matching source/interfaces on both machines.

### 9. Flash only when firmware needs installing

Keep actuator power off while flashing.

1. Hold BOOTSEL while connecting the RP2040 Pico to Windows with a USB data cable.
2. Release BOOTSEL when **RPI-RP2** appears.
3. Extract the complete ZIP and copy **source/firmware/Pico_RP2040_Integrated.uf2** onto RPI-RP2.
4. The Pico normally reboots and the drive disappears.
5. Connect normally to the **Orange Pi USB host port**, without BOOTSEL.

RPI-RP2 is the firmware-loading interface, not the logging SD card. BOOTSEL alone does not erase existing firmware. An Explorer copy error does not establish success; verify Pico status afterward.

The supplied integrated 0.6.0 UF2 has SHA-256:

```text
ac834ef9e70b8027f4b6c7b907f67f61fbaf31e6a2b3c8e2bf14365ecfd35510
```

### 10. Check USB

**Orange Pi SSH**

```bash
python3 -m serial.tools.list_ports -v
sudo fuser -v /dev/ttyACM0
```

Expect **Pico - Pico Serial**. Use its actual port if different.

A bridge, checker and serial monitor must not read the same port simultaneously. Use/stop an existing bridge before starting another tool. With the port free, this optional checker runs without enabling motion:

```bash
cd ~/rover_ws/src/rover_team
python3 tools/pico_link_check.py /dev/ttyACM0 --seconds 15
```

Read each CHECKS field. FAIL can mean SD logging failed even though packets arrived. PASS does not prove physical movement or sensor accuracy. Let the checker exit before starting the bridge.

For serial **Permission denied**:

```bash
sudo usermod -aG dialout "$USER"
```

Log out of SSH and back in so group membership takes effect.

## Daily startup

### A. Connect and check

Power the Pi, connect Ethernet and connect the Pico normally to its USB host port. On the Pi:

```bash
ip -br -4 addr
python3 -m serial.tools.list_ports -v
pgrep -af '[a]rm_bridge'
```

If the address changed, follow [IP changes](#when-the-pi-ip-changes). Use an existing bridge rather than launching a duplicate.

### B. Start the hardware bridge

**Orange Pi SSH — leave running**

```bash
source ~/.config/rover/pi.env
ros2 launch rover_control rover.launch.py \
  dry_run:=false serial_port:=/dev/ttyACM0
```

Closing this terminal can stop the bridge.

### C. Check the Pi locally

**Second Orange Pi SSH terminal**

```bash
source ~/.config/rover/pi.env
timeout 15s ros2 topic echo /arm/status rover_interfaces/msg/ArmStatus --once
timeout 15s ros2 topic echo /arm/sensors rover_interfaces/msg/SensorReadings --once
```

Expect `mode: hardware`, `bridge_mode: serial`, `pico_online: true` and non-simulated sensor messages. `enabled: false` is normal at startup. `operator_online` can remain false until the GUI runs.

### D. Open the GUI

**Laptop Ubuntu/WSL**

```bash
source ~/.config/rover/pc.env
ping -c 3 "$ROVER_PI_IP"
timeout 15s ros2 topic echo /arm/status rover_interfaces/msg/ArmStatus --once
```

Once status appears:

```bash
ros2 launch rover_control ground_station.launch.py
```

Leave the terminal running. Confirm fresh hardware status/readings before enabling. An open window alone does not confirm connection.

### E. Test one servo

1. Turn actuator power off before wiring changes. Use the servo's rated external supply, with ground connected to Pico ground.
2. Support the mechanism and provide clearance. Zero is assumed to be a 1500 µs pulse; enabling can immediately move a misaligned servo.
3. Wait for fresh hardware status, then click **Enable arm**.
4. Command **+1°** on the connected servo's matching GUI axis.
5. If it binds, continuously buzzes or moves unexpectedly, use **STOP ALL OUTPUTS** and remove actuator power.

| Servo signal | Pico GPIO | Physical pin | GUI axis |
| --- | --- | ---: | --- |
| M1 | GP15 | 20 | Axis1 |
| M2 | GP14 | 19 | Axis2 |
| M3 / AXIS_3-1 | GP13 | 17 | Axis3A |
| M4 / AXIS_3-2 | GP12 | 16 | Axis3B |

The commissioning profile uses **−10° to +10°**, provisional **1400–1600 µs** pulses and subsequent motion ramping at **5°/s**. These are not calibrated mechanical angles. The GUI reports targets, not measured position.

Test the DC motor separately. Its 30% duty cap is not measured speed/current limiting. STOP removes servo pulses and zeros the motor command; it does not guarantee a loaded arm holds position.

### F. Shut down

Click **STOP ALL OUTPUTS**, remove actuator power as appropriate, close the GUI and stop the bridge with Ctrl+C. Reconnecting requires a fresh enable. Sensors/logging can run while actuators are stopped.

## Local simulation without the rover

Use two **laptop Ubuntu/WSL** terminals. Domain **42** separates this test from hardware domain 2. No Pi/Pico is needed.

**Terminal 1 — simulated bridge**

```bash
source ~/.config/rover/pc.env
export ROS_DOMAIN_ID=42
unset ROS_STATIC_PEERS
ros2 launch rover_control rover.launch.py dry_run:=true
```

**Terminal 2 — GUI**

```bash
source ~/.config/rover/pc.env
export ROS_DOMAIN_ID=42
unset ROS_STATIC_PEERS
ros2 launch rover_control ground_station.launch.py
```

Expect simulation status and changing commanded targets. This dry-run bridge does not generate live sensor packets, so empty graphs are expected. Simulation does not validate physical motion, sensors, SD, USB or the Pi network path.

Close both simulated processes before hardware testing. Source the normal environment files to restore domain 2 and the peer.

## Sensor, SD and motor wiring

Use the corrected `schematics/two-month-electrical-schematic.svg`. GPIO numbers differ from physical pins.

| Function | Pico GPIO | Physical pin |
| --- | --- | ---: |
| BNO055 + BMP388 SDA | GP4 | 6 |
| BNO055 + BMP388 SCL | GP5 | 7 |
| TB6612 PWMA | GP6 | 9 |
| TB6612 AIN2 | GP7 | 10 |
| TB6612 AIN1 | GP8 | 11 |
| SD MISO / SO | GP16 | 21 |
| SD CS | GP17 | 22 |
| SD SCK | GP18 | 24 |
| SD MOSI / SI | GP19 | 25 |

I2C0 addresses: **BNO055 0x28**, **BMP388 0x77**. Follow the schematic's rails and common ground. Servo/motor load power must not come from a GPIO or the Pico's 3.3 V regulator. The STBY assumption relies on the specified Adafruit breakout's onboard pull-up; verify replacement boards.

The logging SD card needs a supported **FAT32** filesystem. Back up its contents and identify the correct device before reformatting.

## Reading status

| Field | Meaning |
| --- | --- |
| `pico_online: true` | Bridge recently accepted Pico status |
| `operator_online: true` | Bridge recently received the GUI heartbeat |
| `enabled: false` | Actuators stopped; sensors can still publish |
| `ready: true` | Firmware configuration ready; not proof of wiring/calibration |
| `imu_ready` / `bmp_ready` | Firmware init/read checks; verify physical sensor response |
| `sd_ready: true` and increasing `sd_rows` | Mounted card and reported additional logged rows |
| `NO RECENT ARM STATUS` | GUI lacks fresh bridge status |
| `Connection lost` with both online flags true | Can be a retained stop reason; inspect current flags |
| `simulated: false` | Sensor message is marked hardware data |

Units are °C, kPa, m/s² and metres. Altitude is pressure-based and needs a local reference. Three acceleration zeros do not prove a working accelerometer; the configured raw accelerometer normally includes gravity.

## When the Pi IP changes

The Pi changed from `.198` to `.218` after reconnecting.

1. Check `ip -br -4 addr` on the Pi.
2. Run `nano ~/.config/rover/pc.env` on the laptop and update `ROVER_PI_IP`.
3. Re-run step 7's administrator firewall block with the new address.
4. Close/restart the GUI after sourcing `~/.config/rover/pc.env`.

If the laptop Ethernet address changes, edit `ROS_STATIC_PEERS` in the Pi's `pi.env` and restart its bridge too.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| SSH times out | Power, Ethernet, actual IP/sharing; use this Pi's link-local address if DHCP is missing |
| `not a git repository` | `cd ~/rover_ws/src/rover_team` before Git commands |
| Rename says `bad source` | Inspect `ls -l ~/rover_ws/src/rover_team/rover_ros2/rover_control/*bridge*`; do not rename an absent file |
| `No module named rover_control.arm_bridge` | Apply/build the matching update; the filename must be `arm_bridge.py` |
| `source`/`export` not recognized | Open Ubuntu/WSL rather than PowerShell |
| `ros2: command not found` | Source `/opt/ros/jazzy/setup.bash` and check ROS installation |
| Package/interface missing | Build both packages; source `~/rover_ws/install/setup.bash` |
| Pico missing | Data cable, USB host port, normal boot; inspect `lsusb` and `sudo dmesg` |
| RPI-RP2 appears | BOOTSEL; flash the correct UF2 or reconnect normally if already flashed |
| One partial JSON warning at startup | Check whether complete packets follow before changing parsing |
| Repeated truncated/mixed JSON | Check `sudo fuser -v /dev/ttyACM0`; stop competing readers and capture rejected bytes |
| Pi topics work, laptop echo empty | Current IP, both peers/domain/RMW, mirrored WSL and both firewall rules |
| Ping works but ROS does not | Ping tests ICMP, not ROS UDP; check discovery/firewalls |
| GUI opens but fields are blank | Check the bridge process and local Pi topics first |
| Firewall access denied | Use Administrator PowerShell |
| `The daemon is not running` | Informational result of stopping an already-stopped daemon |
| GUI cannot open display | Use laptop WSL/WSLg, not ordinary Pi SSH; check `echo "$DISPLAY"` and WSL updates |
| SD mount failed | Card insertion, FAT32, SPI pins, supply/common ground |
| Target changes, servo does not move | Hardware mode, enabled flag, matching axis/GPIO, supply/ground |

Do not "repair" JSON by blindly adding braces or treating fragments as valid status. First verify exclusive serial ownership and complete newline-delimited packets. The bridge prints `Pico serial framing v2`, its PID and module path at startup.
Malformed JSON logs include the actual byte length and capped beginning/end
excerpts. One invalid initial line can result from opening a stream mid-packet;
repeated damage after that still requires investigation. Advisory serial locking
does not prevent another program that ignores locking from consuming data.

For a debug report, include the computer/terminal, Pi IP, port listing, bridge process/output and local-Pi versus laptop topic results.

## Files and ROS topics

| Path | Purpose |
| --- | --- |
| `rover_interfaces/` | Custom ROS messages |
| `rover_ros2/rover_control/` | GUI, bridge, transport and protocol |
| `rover_ros2/launch/` | Launch files |
| `pico_arduino/rover_pico/` | Arduino C++ firmware |
| `rover_ros2/pico/rover_pico/` | Duplicate firmware; keep both copies synchronized |
| `firmware/` | UF2 images |
| `tools/` | Integrated build/link tools |
| `schematics/` | Corrected drawing |
| `arduino/` and root legacy Python files | Earlier implementation; not the current launch path |

| Topic | Type | Direction |
| --- | --- | --- |
| `/arm/status` | `rover_interfaces/msg/ArmStatus` | Bridge → GUI |
| `/arm/sensors` | `rover_interfaces/msg/SensorReadings` | Bridge → GUI |
| `/arm/joint_command` | `rover_interfaces/msg/JointCommand` | GUI → bridge |
| `/arm/motor_command` | `std_msgs/msg/Float32` | GUI → bridge |
| `/arm/enable` | `std_msgs/msg/Bool` | GUI → bridge |
| `/arm/stop` | `std_msgs/msg/Empty` | GUI → bridge |
| `/arm/heartbeat` | `std_msgs/msg/Bool` | GUI → bridge |

## Updating and publishing

The complete ZIP includes `Commit-To-Git.ps1`. Run it from Windows PowerShell 5
with `-Commit -Push` to clone the current team branch into a new folder, install
this release, stage only its managed files/deletions, commit and push. It uses Git
CLI and leaves an existing OneDrive checkout untouched. Git credentials or author
identity may be requested by Git/the script. No administrator terminal is needed.

```powershell
$roverRelease = Join-Path $env:USERPROFILE ("rover-release-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\Rover_Complete.zip" -DestinationPath $roverRelease
powershell -NoProfile -ExecutionPolicy Bypass -File "$roverRelease\Commit-To-Git.ps1" -Commit -Push
```

Run without `-Commit -Push` to stop after staging and inspect the checkout printed
by the script. A push rejection can mean the team branch advanced or your account
lacks collaborator access. Preserve the new checkout and inspect the error; do not
force-push. SSH keys authenticate an account but do not grant repository access.

The Pi's older checkout may contain local integrated changes. Stop its bridge and
apply the same complete ZIP using step 8 rather than pulling across those edits.
Rebuild on each computer and restart the bridge/GUI. Future source changes to the
Pico need a rebuilt UF2 and reflash; host-only changes do not.

From a clean development checkout, run:

```bash
bash tools/run_tests.sh
```

This needs Python 3, g++ and pySerial for the real POSIX virtual-serial-port test.
The ROS/Qt unit tests use doubles and do not exercise live DDS/GUI rendering.
See `VALIDATION.md` for the release's exact checks and remaining hardware tests.

## References

Release assembled on 24 October 2026; setup references were checked during the 23–24 October setup work.

- [ROS 2 Jazzy installation](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)
- [ROS apt configuration source](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Installation/_Apt-Repositories.rst)
- [Static peers/discovery](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Tutorials/Advanced/Improved-Dynamic-Discovery.rst)
- [Domain IDs and UDP ports](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Concepts/Intermediate/About-Domain-ID.rst)
- [Install WSL](https://learn.microsoft.com/en-us/windows/wsl/install)
- [WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking)
- [WSLg GUI applications](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps)
- [Hyper-V firewall](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/hyper-v-firewall)
- [Pico documentation](https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html)
