# Sensor Monitoring Dashboard (PyQt5)

A real-time desktop dashboard for monitoring industrial sensors (Temperature, Vibration, Speed, Pressure, Optical Counter). The application visualizes data using live graphs, monitors system health (CPU/RAM), and includes an alarm system for critical thresholds.

Two versions are included:
1. Simulation Mode: Generates random test data internally.
2. Serial Mode: Reads real data from an external hardware device (Arduino/PLC) via USB.

---

## 1. Setup Steps

### Prerequisites (For Python Source Code)
* Python 3.8 or higher
* Windows, Linux, or macOS

### Installation
1. Clone or Download the project folder.
2. Open your terminal/command prompt in the project directory.
3. Install the required libraries using pip:

   pip install PyQt5 matplotlib pyserial psutil

   * PyQt5: For the Graphical User Interface (GUI).
   * matplotlib: For real-time plotting of sensor data.
   * pyserial: For communicating with the COM port (Serial Mode only).
   * psutil: For monitoring PC hardware stats (CPU/RAM).

---

## 2. Running Instructions

You can run the application using the Python source code OR the provided executable file.

### Option A: Run Simulation Mode (Python)
Use this version to test the UI logic without connecting physical hardware. It uses multi-threading to generate random noise data.

   python Backend_With_Random_Data.py

### Option B: Run Serial Mode (Python)
Use this version to connect to a real device if you need to modify settings (like COM port) easily.

1. Open the Python script in a text editor.
2. Find the Configuration section at the top:
   SERIAL_PORT = 'COM8'   # <--- CHANGE THIS to your device's port
   SERIAL_RATE = 115200   # Ensure this matches your hardware baud rate
3. Connect your hardware.
4. Run the script:

   python Backend_With_Serial_Data.py

### Option C: Run Serial Mode (Executable)
Use this version for easy deployment without installing Python.

1. Connect your hardware to the computer.
2. Locate the executable file (e.g., `Backend_With_Serial_Data.exe`).
3. Double-click to launch.
   
   *Note: The executable uses the settings compiled into the script (Default: COM8). If your device uses a different port, please use Option B to modify the code first.*

---

## 3. Protocol Description (Serial Format)

The application expects data streams via UART/Serial connection. The hardware must send data lines ending with a newline character (\n).

Protocol Format: ASCII Comma-Separated Values (CSV)
Structure: Temperature,Vibration,Speed,Pressure,OpticalCounter,Timestamp

### Field Definitions:
- Index 0: Temperature   | Type: float | Unit: Celsius
- Index 1: Vibration     | Type: float | Unit: Hz/G
- Index 2: Speed         | Type: float | Unit: RPM
- Index 3: Pressure      | Type: float | Unit: Bar/PSI
- Index 4: Counter       | Type: float | Unit: Count
- Index 5: Timestamp     | Type: string| Format: HH:MM:SS

### Example Valid Packet:
37.5,12.2,88.9,10.5,45,14:30:55

* Packet Handling: If the packet length is not exactly 6 fields, the software logs a "[SERIAL] Invalid packet" warning and discards the data to prevent crashing.

---

## 4. API & Architecture Documentation

### 4.1. Threading Architecture
To ensure the GUI remains responsive, the application uses Python's QThread:

* SerialWorkerThread (Serial Mode):
  - Role: Acts as the driver layer.
  - Function: Continuously polls the serial buffer.
  - Signal: Emits data_received(list, str) containing parsed values and timestamp.
  - Error Handling: Auto-detects disconnection and logs "Critical Serial Error".

* SensorThread (Simulation Mode):
  - Role: Data generator.
  - Function: Runs a loop adding random noise (random.uniform) to a base value.
  - Signal: Emits update_signal(index, value, timestamp).

* SystemMonitorThread:
  - Role: Health check.
  - Function: Uses psutil to query OS-level stats (CPU %, RAM %, HDD Temp).

### 4.2. Alarm Logic API
The MainWindow class implements a logic gate for alarms based on the ALARM_LIMITS dictionary.

Logic Flow:
1. Input: New value arrives.
2. Check: if value < MIN or if value > MAX.
3. Trigger:
   - Update Table Row Color -> Red (#ffcdd2).
   - Log Event -> "CRITICAL ALARM: [Sensor] reached [Value]".
   - System Tray Notification -> Windows Toast Popup.
4. Recovery:
   - If value returns to normal -> Log "RECOVERY" and set Row Color -> Green (#c8e6c9).

### 4.3. Maintenance Console (Security)
* Access Control: The "Maintenance Console" tab is protected.
* Mechanism: QTabWidget signal intercepts the click event.
* Default Password: "admin" (Hardcoded in setup_system_features).