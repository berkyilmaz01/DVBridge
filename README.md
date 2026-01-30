# TCP to AEDAT4 Converter

Convert raw binary event camera frames from custom FPGA/sensor hardware into AEDAT4 format for processing with the DV ecosystem.

## Overview

```text
┌─────────────────┐     ┌─────────────────────────┐     ┌─────────────────┐
│  Custom Event   │────▶│    THIS CONVERTER       │────▶│   DV Software   │
│  Camera/FPGA    │TCP  │                         │TCP  │                 │
│                 │     │  - Receive frames       │     │  - dv-gui       │
│  2-bit packed   │     │  - Unpack to events     │     │  - DV modules   │
│  frames         │     │  - Stream as AEDAT4     │     │  - Recording    │
│  Port: 6000     │     │  Output: 7777           │     │  - Processing   │
└─────────────────┘     └─────────────────────────┘     └─────────────────┘
```

This converter bridges **custom event camera hardware** to the **iniVation DV ecosystem**:
1. **Receives** 2-bit packed frames from FPGA/custom sensor via TCP/UDP
2. **Unpacks** frames into individual events (x, y, timestamp, polarity)
3. **Streams** events as AEDAT4 format to DV software for visualization and processing

---

## When to Use This Converter

### Use This Converter For:
- **Custom FPGA-based event cameras** that output 2-bit packed frame format
- **Research sensors** with non-standard output formats
- **Prototype hardware** that needs DV ecosystem integration
- **Any camera** that outputs the specific 2-bit packed format described below

### NOT Needed For:
- **Commercial iniVation cameras** (DVXplorer, DAVIS, etc.) - these already output AEDAT4 natively
- **Prophesee cameras** - use their SDK or convert to AEDAT4 directly
- **Standard event cameras** with native AEDAT4 or similar output

---

## Quick Start - Commands to Run

### One-Time Installation

```bash
# Install DV software suite (Ubuntu)
sudo add-apt-repository ppa:inivation-ppa/inivation
sudo apt update
sudo apt install -y build-essential cmake dv-processing dv-gui

# Build the converter
cd ~/tcp-to-aedat4-converter
mkdir build && cd build
cmake ..
make
```

### Running the Pipeline (3 Terminals)

Open 3 terminal windows and run these commands:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ TERMINAL 1: Start Converter                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ cd ~/tcp-to-aedat4-converter/build                                          │
│ ./converter                                                                 │
│                                                                             │
│ (Waits for camera on port 6000, serves AEDAT4 on port 7777)                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ TERMINAL 2: Start DV Viewer                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ dv-gui                                                                      │
│                                                                             │
│ In DV-GUI:                                                                  │
│   1. Click "Add Module" → "Input" → "Network TCP Client"                    │
│   2. Set IP: 127.0.0.1, Port: 7777                                          │
│   3. Click Play button                                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ TERMINAL 3: Start Camera (or use test simulator)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ # FOR TESTING (without real hardware):                                      │
│ cd ~/tcp-to-aedat4-converter                                                │
│ python3 test/fake_camera.py                                                 │
│                                                                             │
│ # FOR REAL HARDWARE:                                                        │
│ # Start your FPGA/camera - it should connect to PC_IP:6000                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```text
Terminal 3              Terminal 1              Terminal 2
(Camera/FPGA)           (Converter)             (DV Viewer)
     │                       │                       │
     │   2-bit frames        │                       │
     │──────────────────────▶│                       │
     │      port 6000        │                       │
     │                       │   AEDAT4 events       │
     │                       │──────────────────────▶│
     │                       │      port 7777        │
     │                       │                       │
                                              ┌──────────────┐
                                              │ Visualize    │
                                              │ Record       │
                                              │ Process      │
                                              │ Analyze      │
                                              └──────────────┘
```

---

## Full Pipeline Setup Guide

### Prerequisites

| Component | Purpose |
|-----------|---------|
| Ubuntu 20.04+ / Windows 10+ | Supported operating systems |
| Custom Event Camera | FPGA/sensor outputting 2-bit packed frames |
| Ethernet Connection | Direct or via switch to camera |
| DV Processing | AEDAT4 encoding library |
| DV GUI | Visualization and processing modules |

---

### Linux/Ubuntu Installation

#### Step 1: Install DV Software Suite

```bash
# Update package list
sudo apt update

# Add iniVation repository (contains dv-processing and dv-gui)
sudo add-apt-repository ppa:inivation-ppa/inivation
sudo apt update

# Install DV ecosystem
sudo apt install -y build-essential cmake git python3
sudo apt install -y dv-processing dv-gui

# Verify installation
dv-gui --version
```

#### Step 2: Build the Converter

```bash
# Clone repository
cd ~
git clone https://github.com/berkyilmaz01/tcp-to-aedat4-converter.git
cd tcp-to-aedat4-converter

# Build
mkdir build && cd build
cmake ..
make

# Verify build
ls -la converter  # Should show the executable
```

---

### Windows Installation

#### Step 1: Install Prerequisites

1. **Visual Studio 2019 or newer**
   - Download from: https://visualstudio.microsoft.com/
   - During installation, select **"Desktop development with C++"** workload

2. **CMake 3.14+**
   - Download from: https://cmake.org/download/
   - Add to PATH during installation

3. **vcpkg (Package Manager)**
   ```powershell
   cd C:\
   git clone https://github.com/Microsoft/vcpkg.git
   cd vcpkg
   .\bootstrap-vcpkg.bat
   .\vcpkg integrate install
   ```

#### Step 2: Install Dependencies

```powershell
cd C:\vcpkg

# Install dv-processing and OpenCV (this may take 15-30 minutes)
.\vcpkg install dv-processing:x64-windows
.\vcpkg install opencv4:x64-windows
```

#### Step 3: Install DV-GUI

Download and install DV-GUI from iniVation:
- https://docs.inivation.com/software/dv/dv-gui.html
- Run the Windows installer (.exe)

#### Step 4: Build the Converter

```powershell
# Clone repository
cd %USERPROFILE%
git clone https://github.com/berkyilmaz01/tcp-to-aedat4-converter.git
cd tcp-to-aedat4-converter

# Create build directory
mkdir build
cd build

# Configure with vcpkg toolchain
cmake .. -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake

# Build
cmake --build . --config Release

# Verify build
dir Release\converter.exe
```

#### Step 5: Allow Through Firewall

Windows Firewall may block the network ports. Allow them:

1. Open **Windows Defender Firewall**
2. Click **"Allow an app through firewall"**
3. Add `converter.exe` and allow both Private and Public networks
4. Or run in PowerShell (Admin):
   ```powershell
   netsh advfirewall firewall add rule name="DVBridge 6000" dir=in action=allow protocol=tcp localport=6000
   netsh advfirewall firewall add rule name="DVBridge 7777" dir=in action=allow protocol=tcp localport=7777
   ```

#### Running on Windows

```powershell
# Terminal 1: Start converter
cd tcp-to-aedat4-converter\build\Release
.\converter.exe

# Terminal 2: Start DV-GUI
# Launch from Start Menu or run:
"C:\Program Files\iniVation\dv-gui\dv-gui.exe"

# Terminal 3: Test with simulator
cd tcp-to-aedat4-converter
python test\fake_camera.py
```

---

### Step 3: Configure for Your Hardware

Edit the configuration file to match your camera specifications:

```bash
nano ~/tcp-to-aedat4-converter/include/config.hpp
```

**Critical Settings:**

```cpp
// Frame dimensions - MUST match your sensor
int width = 1280;           // Sensor width in pixels
int height = 720;           // Sensor height in pixels

// Network settings
Protocol protocol = Protocol::TCP;  // TCP or UDP
int camera_port = 6000;             // Port where FPGA connects
int aedat_port = 7777;              // Port for DV software connection

// Timing - MUST match your camera's frame rate
int64_t frame_interval_us = 10000;  // 10000us = 100 FPS
                                     // 1000us = 1000 FPS
                                     // 100us = 10000 FPS
```

Rebuild after configuration changes:
```bash
cd ~/tcp-to-aedat4-converter/build
make
```

---

## Running the Full Pipeline

### Option A: Basic Visualization (3 Terminals)

**Terminal 1 - Start Converter:**
```bash
cd ~/tcp-to-aedat4-converter/build
./converter
```

Expected output:
```text
============================================
   TCP/UDP to AEDAT4 Converter
============================================

Configuration:
  Protocol: TCP
  Frame size: 1280 x 720
  Frame data size: 230400 bytes
  TCP Server port: 6000 (FPGA connects here)
  AEDAT4 output port: 7777
  Frame interval: 10000 us
  Has header: no
  Pixel format: 2-bit packed (FPGA format)

Starting AEDAT4 server on port 7777...
AEDAT4 server started. DV viewer can connect to port 7777

Starting TCP server (waiting for FPGA connection)...
```

**Terminal 2 - Start DV Visualization:**
```bash
dv-gui
```

Configure DV-GUI:
1. Click **"Add Module"** (top left)
2. Select **"Input"** → **"Network TCP Client"**
3. Set **IP Address**: `127.0.0.1`
4. Set **Port**: `7777`
5. Click the **Play** button

**Terminal 3 (or Camera Side) - Send Data:**
For testing without hardware:
```bash
cd ~/tcp-to-aedat4-converter
python3 test/realistic_camera.py --scene objects --fps 100
```

For real hardware: Start your FPGA/camera to connect to the converter IP on port 6000.

### Option B: Full DV Processing Pipeline

DV-GUI supports modular processing chains. Here's a recommended setup:

```text
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Network TCP  │────▶│ Accumulator  │────▶│ Visualizer   │────▶│ AEDAT4       │
│ Client       │     │ (optional)   │     │              │     │ Writer       │
│ Port: 7777   │     │              │     │              │     │ (recording)  │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

**Setting up a processing chain in DV-GUI:**

1. **Input Module** (Network TCP Client)
   - IP: `127.0.0.1`, Port: `7777`

2. **Processing Modules** (optional):
   - **Accumulator**: Integrates events into frames
   - **Event Filter**: Noise reduction, ROI selection
   - **Refractory Filter**: Remove redundant events
   - **Background Activity Filter**: Remove hot pixels

3. **Visualizer**: Real-time event display

4. **Output Module** (AEDAT4 Writer): Record to file for offline analysis

---

## Hardware Connection Guide

### Network Configuration

**Direct Ethernet Connection (Recommended):**
```text
┌─────────────┐                    ┌─────────────┐
│   PC        │◄──── Ethernet ────▶│   FPGA/     │
│             │                    │   Camera    │
│ IP: 192.168.50.20               │ IP: 192.168.50.10
│ Converter listens: 6000          │ Connects to: 192.168.50.20:6000
└─────────────┘                    └─────────────┘
```

Configure PC network interface:
```bash
# Set static IP (replace eth0 with your interface)
sudo ip addr add 192.168.50.20/24 dev eth0
sudo ip link set eth0 up
```

**Through Network Switch:**
- Connect both devices to same switch
- Ensure same subnet (e.g., 192.168.50.x)
- Firewall must allow port 6000 (input) and 7777 (local)

### FPGA/Camera Requirements

Your hardware must output data in this **2-bit packed pixel format**:

```text
Each pixel = 2 bits:
  00 = no event
  01 = positive polarity (brightness increased)
  10 = negative polarity (brightness decreased)
  11 = unused

4 pixels per byte, MSB first:
  Byte: [pixel0][pixel1][pixel2][pixel3]
        bits7-6 bits5-4 bits3-2 bits1-0

Frame size = (width × height + 3) / 4 bytes
Example: 1280×720 = 230,400 bytes per frame
```

**FPGA Implementation Reference:**
```cpp
// Function to set a pixel in the frame buffer
static inline void set_pixel(uint8_t *frame, int x, int y, int polarity) {
    const size_t pixel_index = (size_t)y * WIDTH + (size_t)x;
    const size_t byte_index  = pixel_index >> 2;  // divide by 4
    const int    shift       = (3 - (pixel_index & 3)) * 2;
    const uint8_t v = (polarity == 0) ? 0b10 : 0b01;  // 0→neg, 1→pos
    frame[byte_index] = (frame[byte_index] & ~(0b11 << shift)) | (v << shift);
}
```

---

## Data Flow & Timestamps

### How Events Are Generated

```text
FPGA sends:     Frame N (230,400 bytes) at time T
                Frame N+1 (230,400 bytes) at time T + frame_interval

Converter:      For each non-zero pixel in frame N:
                  - Extract x, y from pixel position
                  - Extract polarity from 2-bit value
                  - Assign timestamp = N × frame_interval_us
                  - Create Event(timestamp, x, y, polarity)

Output:         AEDAT4 event stream to DV software
```

### Timestamp Accuracy

Timestamps are frame-based, not per-event:
- All events in a frame share the same timestamp
- Temporal resolution = frame_interval_us
- For 100 FPS: 10ms temporal resolution
- For 10,000 FPS: 100μs temporal resolution

**Important:** Set `frame_interval_us` to match your camera's actual frame rate for accurate timestamps.

---

## Testing Without Hardware

### Included Simulators

| Simulator | Description | Use Case |
|-----------|-------------|----------|
| `fake_camera.py` | Basic TCP simulator | Quick testing |
| `fake_camera_udp.py` | UDP simulator | UDP mode testing |
| `realistic_camera.py` | Advanced patterns | Realistic testing |
| `fast_fake_camera.py` | High-speed testing | Performance testing |

### Test Procedure

**Terminal 1 - Converter:**
```bash
cd ~/tcp-to-aedat4-converter/build
./converter
```

**Terminal 2 - DV Viewer:**
```bash
dv-gui
# Add Network TCP Client module, connect to 127.0.0.1:7777
```

**Terminal 3 - Simulator:**
```bash
cd ~/tcp-to-aedat4-converter

# Basic test (moving circles)
python3 test/fake_camera.py

# Realistic bouncing objects
python3 test/realistic_camera.py --scene objects --fps 100

# Text display
python3 test/realistic_camera.py --scene dots --text "HELLO" --fps 100
```

---

## DV Processing Integration

### Available DV Modules

Once events are streamed via this converter, you can use all DV-GUI modules:

| Category | Modules |
|----------|---------|
| **Visualization** | Event Visualizer, Frame Accumulator, 3D Visualizer |
| **Filtering** | Noise Filter, Refractory Filter, ROI Filter, Polarity Filter |
| **Analysis** | Event Statistics, Rate Meter, Histogram |
| **Recording** | AEDAT4 Writer, AVI Writer, CSV Export |
| **Processing** | Optical Flow, Feature Detection, Tracking |

### Example: Recording Events

1. Add **"Network TCP Client"** (IP: 127.0.0.1, Port: 7777)
2. Add **"AEDAT4 File Writer"** and connect to input
3. Click record to save events to `.aedat4` file
4. Playback later with **"AEDAT4 File Reader"** module

### Programmatic Access (Python)

```python
import dv_processing as dv

# Connect to converter output
client = dv.io.NetworkReader("127.0.0.1", 7777)

# Read events
while True:
    events = client.getNextEventBatch()
    if events is not None:
        print(f"Received {len(events)} events")
        # Process events...
```

### Programmatic Access (C++)

```cpp
#include <dv-processing/io/network_reader.hpp>

dv::io::NetworkReader reader("127.0.0.1", 7777);

while (true) {
    auto events = reader.getNextEventBatch();
    if (events.has_value()) {
        std::cout << "Received " << events->size() << " events" << std::endl;
        // Process events...
    }
}
```

---

## Troubleshooting

### Connection Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Waiting for FPGA connection..." | Camera not connecting | Check IP/port config on camera side |
| No events in DV viewer | DV on wrong port | Ensure DV connects to port 7777 (not 6000) |
| Connection refused | Firewall blocking | Allow ports 6000 and 7777 |
| "Reconnection failed" | Network timeout | Check Ethernet cable, IP addresses |

### Data Quality Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| Random noise pattern | Frame size mismatch | Verify width/height match sensor |
| No events visible | All pixels are zero | Check camera is generating events |
| Events at wrong positions | Byte order mismatch | Verify MSB-first pixel ordering |
| Timing looks wrong | Incorrect frame_interval | Match frame_interval_us to actual FPS |

### Performance Issues

| Symptom | Solution |
|---------|----------|
| Low throughput | Use wired Ethernet, not WiFi |
| Dropped frames | Increase `recv_buffer_size` in config |
| High latency | Use direct Ethernet connection |
| DV-GUI lag | Reduce accumulator frame rate |

---

## Quick Reference

### Commands
```bash
# Build converter
cd ~/tcp-to-aedat4-converter/build && make

# Run converter
./converter

# Run with verbose output
# (set verbose = true in config.hpp, then rebuild)

# Test simulators
python3 test/fake_camera.py
python3 test/realistic_camera.py --scene objects --fps 100

# Launch DV
dv-gui
```

### Network Ports

| Port | Direction | Description |
|------|-----------|-------------|
| 6000 | Camera → Converter | Raw 2-bit packed frames |
| 7777 | Converter → DV | AEDAT4 event stream |

### Configuration File

`include/config.hpp` - All settings:
- Frame: width, height
- Network: camera_port, aedat_port, protocol
- Timing: frame_interval_us
- Debug: stats_interval, verbose

---

## Technical Specifications

| Parameter | Value |
|-----------|-------|
| Input Protocol | TCP or UDP |
| Input Format | 2-bit packed pixels (4 pixels/byte) |
| Output Protocol | TCP (AEDAT4 stream) |
| Output Format | AEDAT4 (dv-processing NetworkWriter) |
| Default Resolution | 1280 × 720 |
| Default Frame Size | 230,400 bytes |
| Default Frame Rate | 100 FPS |
| Supported OS | Linux (Ubuntu 20.04+), Windows 10+, macOS |

---

## Additional Resources

- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical design documentation
- [iniVation DV Documentation](https://docs.inivation.com/)
- [dv-processing API](https://dv-processing.docs.inivation.com/)

## License

MIT License

## Contact

Berk Yilmaz
