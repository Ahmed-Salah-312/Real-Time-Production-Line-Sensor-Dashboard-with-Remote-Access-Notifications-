import sys
import time
import random
from datetime import datetime
import serial  # <--- Library required to communicate with COM ports (USB/Serial)

# --- Import psutil for system hardware stats ---
# We wrap this in a try-except block because 'psutil' is not a standard Python library.
# If the user hasn't installed it, the program gracefully exits with an error message.
try:
    import psutil
except ImportError:
    print("CRITICAL: 'psutil' library not found. Please install it using: pip install psutil")
    sys.exit(1)

# PyQt Imports
# These manage the Graphical User Interface (GUI), windows, buttons, and tables.
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableWidgetItem, QMessageBox,
    QInputDialog, QSystemTrayIcon, QMenu, QHeaderView,
    QVBoxLayout, QPushButton, QDialog, QHBoxLayout, QSizePolicy, QWidget
)
# QThread is used to run code in the background without freezing the GUI.
# pyqtSignal is used to send data from background threads to the main window.
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QColor, QIcon

# Matplotlib Imports
# Used for embedding the real-time graphs into the PyQt window.
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Project Imports
# Importing the visual layout (front.py) and custom pop-up dialogs (Dialogs.py)
from front import Ui_MainWindow
from Dialogs import Set_Password_Dialog, Show_Access_Denied, Show_Access_Granted

# --- CONFIGURATION ---
# These constants define the environment settings.
SERIAL_PORT = 'COM8'  # The specific USB port the hardware is connected to.
SERIAL_RATE = 115200  # The speed of data transmission (Baud Rate).
SENSOR_NAMES = ["Temperature", "Vibration", "Speed", "Pressure", "Optical Counter"]
# Placeholder values to show before the first real packet arrives.
INITIAL_VALUES = [0.0, 0.0, 0.0, 0.0, 0.0]

# Defines the Safe Operating Area for each sensor.
# Format: Index: (Lower Limit, Upper Limit)
ALARM_LIMITS = {
    0: (20.0, 45.0),  # Temperature
    1: (0.0, 50.0),  # Vibration
    2: (0.0, 150.0),  # Speed
    3: (5.0, 15.0),  # Pressure
    4: (0.0, 1000.0)  # Optical Counter
}


# --- 1. SERIAL WORKER THREAD ---
# This class runs in the background. It listens to the COM port so the Main Window doesn't freeze.
class SerialWorkerThread(QThread):
    # Signals allow this thread to "shout" data to the Main Window.
    data_received = pyqtSignal(list, str)  # Sends [values], timestamp
    log_signal = pyqtSignal(str)  # Sends status messages (Connected, Error, etc.)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.ser = None

    def run(self):
        """The main loop of the background thread."""
        try:
            # Attempt to open the connection to the hardware
            self.ser = serial.Serial(SERIAL_PORT, SERIAL_RATE, timeout=1)
            self.log_signal.emit(f"<b>[SERIAL]</b> Connected to {SERIAL_PORT} successfully.")

            while self.is_running:
                # Check if there is data waiting in the buffer
                if self.ser.in_waiting > 0:
                    try:
                        # 1. READ & CLEAN: Read raw bytes, decode to text, remove whitespace
                        raw_line = self.ser.readline().decode('utf-8', errors='ignore').strip()

                        # 2. PARSE: Split the string by commas
                        # Expected format: "Temp,Vib,Speed,Press,Count,Time"
                        parts = raw_line.split(',')

                        if len(parts) == 6:
                            # Convert the first 5 parts to Numbers (Floats)
                            values = [float(x) for x in parts[:5]]
                            timestamp = parts[5]

                            # Send the clean data to the GUI
                            self.data_received.emit(values, timestamp)
                        else:
                            # If data length is wrong (noise or bad packet), log a warning
                            if raw_line:
                                self.log_signal.emit(
                                    f"<span style='color:orange'>[SERIAL] Invalid packet len: {raw_line}</span>")

                    except ValueError:
                        # Handle cases where data is not a number (corruption)
                        self.log_signal.emit(f"<span style='color:red'>[SERIAL] Parse Error: {raw_line}</span>")
                else:
                    # Sleep briefly to save CPU power if no data is present
                    time.sleep(0.01)

        except serial.SerialException as e:
            # Handle physical connection errors (unplugged cable, wrong port)
            self.log_signal.emit(f"<span style='color:red'><b>[SERIAL CRITICAL]</b> Could not open port: {e}</span>")
        except Exception as e:
            self.log_signal.emit(f"<span style='color:red'><b>[SERIAL ERROR]</b> {e}</span>")
        finally:
            # Ensure the port closes properly when the thread stops
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.log_signal.emit("<b>[SERIAL]</b> Port closed.")

    def stop(self):
        """Safely stops the loop."""
        self.is_running = False
        self.wait()


# --- 2. SYSTEM MONITOR THREAD ---
# Monitors the PC's own health (CPU, RAM, HDD) independently of the sensors.
class SystemMonitorThread(QThread):
    stats_signal = pyqtSignal(str)

    def run(self):
        while True:
            # Get CPU and RAM usage percentages
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent

            # Attempt to read HDD temperature (Complex on Windows, requires Admin usually)
            hdd_temp = "N/A"
            try:
                temps = psutil.sensors_temperatures()
                if 'drivetemp' in temps:
                    hdd_entry = temps['drivetemp'][0]
                    hdd_temp = f"{hdd_entry.current}°C"
                else:
                    # Fallback to simulation if sensor not readable
                    hdd_temp = f"{random.randint(30, 45)}°C (Sim)"
            except Exception:
                hdd_temp = f"{random.randint(30, 45)}°C (Sim)"

            # Create an HTML formatted string for the log
            msg = (f"<span style='color:blue'><b>[HARDWARE]</b></span> "
                   f"CPU: {cpu}% | RAM: {ram}% | HDD: {hdd_temp}")

            self.stats_signal.emit(msg)
            time.sleep(10)  # Update every 10 seconds


# --- MAXIMIZE DIALOG ---
# A helper window that pops up when a user clicks "Maximize" on a graph.
class MaximizeDialog(QDialog):
    def __init__(self, canvas, title, original_layout, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{title} - Maximized View")
        self.resize(900, 600)

        # We "borrow" the plot canvas from the main window
        self.canvas = canvas
        self.original_layout = original_layout

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)  # Add canvas to this popup

    def closeEvent(self, event):
        # When closing, we MUST give the canvas back to the main window
        self.original_layout.addWidget(self.canvas)
        event.accept()


# --- MAIN WINDOW ---
# The core application logic.
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Load the visual design created in Qt Designer (front.py)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Cleanup: Remove tab_4 if it exists (usually an empty placeholder)
        if hasattr(self.ui, 'tab_4'):
            index_of_tab_4 = self.ui.tabWidget.indexOf(self.ui.tab_4)
            if index_of_tab_4 != -1:
                self.ui.tabWidget.removeTab(index_of_tab_4)

        # Configure Table visuals (stretch headers to fill space)
        self.ui.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ui.tableWidget.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setup_table_items()
        self.setup_system_features()

        # --- BUTTON CONNECTIONS ---
        # Link UI Buttons to specific Python functions
        self.ui.Clear_Alarms_Button.clicked.connect(self.clear_alarm_log)
        self.ui.Restart_Simulation_Button.clicked.connect(self.reset_graphs)
        self.ui.Force_Refresh_Button.clicked.connect(self.force_refresh)
        self.ui.Snapshot_of_Values_Button.clicked.connect(self.snapshot_values)
        self.ui.Clear_Alarms_Maintainance_Button.clicked.connect(self.clear_maintenance_log)

        # Initialize State Variables
        self.active_alarms = [False] * 5  # Tracks if a specific sensor is currently in alarm
        self.latest_values = list(INITIAL_VALUES)
        self.update_global_status_label()

        # Setup Plotting Areas
        self.views = [
            self.ui.temp_graphicsView,
            self.ui.vibration_graphicsView,
            self.ui.speed_graphicsView,
            self.ui.pressure_graphicsView,
            self.ui.optical_counters_graphicsView
        ]
        self.axes, self.canvases, self.layouts = [], [], []
        self.maximized_windows = []
        self.sensor_histories = [[] for _ in range(5)]  # Stores data points for the lines

        # Initialize the graphs for all sensors
        for view, title in zip(self.views, SENSOR_NAMES):
            canvas, ax, layout = self.setup_plot(view, title)
            self.canvases.append(canvas)
            self.axes.append(ax)
            self.layouts.append(layout)

        # --- START SERIAL THREAD ---
        self.log_system_event("<b>[SYSTEM]</b> Application Started. Connecting to Serial...")

        # Create and start the worker thread for serial communication
        self.serial_thread = SerialWorkerThread()
        # Connect signals: When thread gets data, call 'process_serial_packet'
        self.serial_thread.data_received.connect(self.process_serial_packet)
        self.serial_thread.log_signal.connect(self.log_system_event)
        self.serial_thread.start()

        # Start the background PC health monitor
        self.monitor_thread = SystemMonitorThread()
        self.monitor_thread.stats_signal.connect(self.log_system_event)
        self.monitor_thread.start()

    def setup_table_items(self):
        """Initializes the table with sensor names and 'Waiting' status."""
        for i, (name, val) in enumerate(zip(SENSOR_NAMES, INITIAL_VALUES), 1):
            # Column 0: Sensor Name
            item_name = QTableWidgetItem(name)
            item_name.setTextAlignment(Qt.AlignCenter)
            self.ui.tableWidget.setItem(i, 0, item_name)

            # Column 1: Value
            item_val = QTableWidgetItem(str(val))
            item_val.setTextAlignment(Qt.AlignCenter)
            self.ui.tableWidget.setItem(i, 1, item_val)

            # Column 3: Status (Waiting for data)
            self.update_status_gui(i, "WAITING", QColor("#e0e0e0"))

    def setup_system_features(self):
        """Sets up the System Tray icon (bottom right of Windows taskbar)."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("../logo2424.png"))

        # Right-click menu for the tray icon
        tray_menu = QMenu()
        tray_menu.addAction("Show").triggered.connect(self.show)
        tray_menu.addAction("Quit").triggered.connect(QApplication.quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # Password configuration
        self.maintenance_password = "admin"
        self.last_tab_index = 0
        # Watch for tab changes to trigger password check
        self.ui.tabWidget.currentChanged.connect(self.check_maintenance_access)

    def setup_plot(self, view, title):
        """Creates a Matplotlib canvas and embeds it into a specific UI widget."""
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)

        # Add the 'Maximize' button above the graph
        header = QHBoxLayout()
        header.addStretch()
        btn = QPushButton("Maximize")
        btn.setStyleSheet("font-size: 10px; padding: 2px 8px;")
        header.addWidget(btn)
        layout.addLayout(header)

        # Create the Matplotlib Figure
        fig = Figure()
        fig.subplots_adjust(left=0.15, right=0.95, top=0.9, bottom=0.2)
        ax = fig.add_subplot(111)
        ax.grid(True, linestyle='--', alpha=0.5)

        # Create the Canvas (the widget that holds the figure)
        canvas = FigureCanvas(fig)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(canvas)

        # Link the button to the maximize logic
        btn.clicked.connect(lambda _, c=canvas, t=title, l=layout: self.maximize_plot(c, t, l))
        return canvas, ax, layout

    def maximize_plot(self, canvas, title, layout):
        """Moves the plot canvas into a popup dialog for better viewing."""
        self.log_system_event(f"<b>[UI]</b> User maximized plot: {title}")
        dialog = MaximizeDialog(canvas, title, layout, self)
        dialog.show()
        self.maximized_windows.append(dialog)
        # Clean up list when closed
        dialog.finished.connect(
            lambda: self.maximized_windows.remove(dialog) if dialog in self.maximized_windows else None)

    # --- NEW: PROCESS SERIAL DATA ---
    def process_serial_packet(self, values_list, timestamp):
        """Receives the full packet of 5 values and updates all sensors."""
        # Loop through indices 0 to 4
        for i in range(5):
            self.handle_sensor_update(i, values_list[i], timestamp)

    # --- CORE SENSOR LOGIC ---
    def handle_sensor_update(self, index, value, timestamp):
        """Updates the Table, Alarms, and Graphs for a SINGLE sensor."""
        self.latest_values[index] = value
        row = index + 1

        # 1. Update Table Value
        item = self.ui.tableWidget.item(row, 1)
        if item: item.setText(f"{value:.2f}")

        # 2. Update Table Timestamp
        item_time = QTableWidgetItem(timestamp)
        item_time.setTextAlignment(Qt.AlignCenter)
        self.ui.tableWidget.setItem(row, 2, item_time)

        # 3. Check for Alarms
        self.check_and_log_alarm(index, value, timestamp, row)

        # 4. Update Graphs
        current_dt = datetime.now()
        # Add new point to history
        self.sensor_histories[index].append((current_dt, value))
        # Keep only the last 20 points (scrolling window)
        if len(self.sensor_histories[index]) > 20: self.sensor_histories[index].pop(0)

        # Redraw the plot
        times_dt, values = zip(*self.sensor_histories[index])
        times_str = [t.strftime("%S") for t in times_dt]  # Show only Seconds on X-axis

        ax = self.axes[index]
        ax.cla()  # Clear previous line
        ax.plot(times_str, values, 'b-', marker='.')  # Plot new line
        ax.grid(True, alpha=0.5)
        self.canvases[index].draw()  # Refresh canvas

    def check_and_log_alarm(self, index, value, timestamp, row):
        """Compares value against ALARM_LIMITS and triggers alerts if needed."""
        low_limit, high_limit = ALARM_LIMITS.get(index, (0, 9999))
        sensor_name = SENSOR_NAMES[index]
        alarm_type = None

        # Determine if value is out of bounds
        if value < low_limit:
            alarm_type = "LOW Limit Triggered"
        elif value > high_limit:
            alarm_type = "HIGH Limit Triggered"

        was_active = self.active_alarms[index]
        is_active = (alarm_type is not None)

        if is_active:
            # --- ALARM STATE ---
            self.active_alarms[index] = True
            # Set table row to RED
            self.update_status_gui(row, "CRITICAL", QColor("#ffcdd2"))
            self.add_alarm_entry(timestamp, sensor_name, value, alarm_type)

            if not was_active:
                # Trigger Notification only on the rising edge (when it FIRST goes bad)
                self.tray_icon.showMessage(
                    "CRITICAL ALARM",
                    f"{sensor_name} reached {value:.2f} ({alarm_type})",
                    QSystemTrayIcon.Critical,
                    3000
                )
                self.log_system_event(
                    f"<span style='color:red'><b>[ALARM]</b> {sensor_name} went critical! Value: {value:.2f} ({alarm_type})</span>")

        else:
            # --- NORMAL STATE ---
            self.active_alarms[index] = False
            # Set table row to GREEN
            self.update_status_gui(row, "OK", QColor("#c8e6c9"))

            if was_active:
                # Log recovery message
                self.log_system_event(
                    f"<span style='color:green'><b>[RECOVERY]</b> {sensor_name} returned to normal range. Value: {value:.2f}</span>")

        # Update the big main status banner
        self.update_global_status_label()

    def update_global_status_label(self):
        """Updates the big banner at the top based on if ANY alarm is active."""
        if any(self.active_alarms):
            self.ui.System_Status_label.setText("System Status : Alarm Active")
            self.ui.System_Status_label.setStyleSheet("""
                background-color: red; color: white; font-weight: bold; 
                font-size: 16px; border-radius: 5px; padding: 5px;
            """)
        else:
            self.ui.System_Status_label.setText("System Status : No Alarms")
            self.ui.System_Status_label.setStyleSheet("""
                background-color: #4caf50; color: white; font-weight: bold; 
                font-size: 16px; border-radius: 5px; padding: 5px;
            """)

    def update_status_gui(self, row, text, color):
        """Helper to change the text and background color of the status column."""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setBackground(color)
        self.ui.tableWidget.setItem(row, 3, item)

    def add_alarm_entry(self, time_str, name, value, alarm_type):
        """Adds a line to the 'Alarm Log' text browser."""
        log_entry = (
            f"<span style='color: #555;'>[{time_str}]</span> "
            f"<b>{name}:</b> {value:.2f} — "
            f"<span style='color: red; font-weight: bold;'>{alarm_type}</span>"
        )
        self.ui.Alarm_Log_textBrowser.append(log_entry)
        self.ui.Alarm_Log_textBrowser.moveCursor(self.ui.Alarm_Log_textBrowser.textCursor().End)

    def clear_alarm_log(self):
        """Clears the Alarm Log text browser."""
        self.ui.Alarm_Log_textBrowser.clear()
        self.log_system_event("<b>[USER]</b> Alarm Log cleared by user.")

    def log_system_event(self, message):
        """Adds a line to the 'Live Log' text browser (General events)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"<span style='color: #666;'>[{timestamp}]</span> {message}"
        self.ui.Live_Log_Viewer_textBrowser.append(formatted_msg)
        self.ui.Live_Log_Viewer_textBrowser.moveCursor(self.ui.Live_Log_Viewer_textBrowser.textCursor().End)

    def clear_maintenance_log(self):
        """Clears the Live Log."""
        self.ui.Live_Log_Viewer_textBrowser.clear()
        self.log_system_event("<b>[USER]</b> Maintenance Logs cleared.")

    def reset_graphs(self):
        """Clears all historical data from the plots."""
        self.log_system_event("<b>[ACTION]</b> Graph Reset requested.")
        self.sensor_histories = [[] for _ in range(5)]  # Empty the data arrays
        for ax, canvas in zip(self.axes, self.canvases):
            ax.cla()
            ax.grid(True, alpha=0.5)
            canvas.draw()
        self.log_system_event("<b>[ACTION]</b> Graphs Cleared.")

    def force_refresh(self):
        """Redraws the graphs without clearing data (useful if UI glitch)."""
        self.log_system_event("<b>[ACTION]</b> Force Refresh triggered.")
        for ax, canvas in zip(self.axes, self.canvases):
            ax.cla()
            ax.grid(True, alpha=0.5)
            canvas.draw()

    def snapshot_values(self):
        """Prints current values of all sensors to the log."""
        self.log_system_event("<b>[ACTION]</b> Snapshot requested.")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"<br><b>--- SNAPSHOT AT {timestamp} ---</b><br>"
        for i, name in enumerate(SENSOR_NAMES):
            val = self.latest_values[i]
            log_msg += f"{name}: {val:.2f}<br>"
        log_msg += "-------------------------------------<br>"
        self.log_system_event(log_msg)

    # --- MAINTENANCE ACCESS ---
    def check_maintenance_access(self, index):
        # We use a small timer to allow the tab click to register before checking
        QTimer.singleShot(10, lambda: self._deferred_check(index))

    def _deferred_check(self, index):
        """Checks if the user clicked the 'Maintenance Console' tab."""
        if self.ui.tabWidget.tabText(index) == "Maintenance Console":
            self.log_system_event("<b>[SECURITY]</b> Access attempt to Maintenance Console...")

            # Hide content temporarily
            page = self.ui.tabWidget.widget(index)
            page.setVisible(False)

            # Show Password Dialog
            pwd, ok = Set_Password_Dialog(self)

            if ok and pwd == self.maintenance_password:
                self.log_system_event("<b>[SECURITY]</b> Access GRANTED.")
                page.setVisible(True)
                Show_Access_Granted(self)
                self.last_tab_index = index
            else:
                if ok:
                    self.log_system_event(
                        "<span style='color:red'><b>[SECURITY]</b> Access DENIED (Incorrect Password).</span>")
                    Show_Access_Denied(self)
                else:
                    self.log_system_event("<b>[SECURITY]</b> Access Cancelled.")

                # Revert to the previous tab
                page.setVisible(True)
                self.ui.tabWidget.blockSignals(True)  # Stop signal loop
                self.ui.tabWidget.setCurrentIndex(self.last_tab_index)
                self.ui.tabWidget.blockSignals(False)
        else:
            self.last_tab_index = index

    def closeEvent(self, event):
        """Handles what happens when the user clicks 'X'."""
        self.log_system_event("<b>[SYSTEM]</b> Shutting down application...")
        # Stop the serial thread gracefully
        if hasattr(self, 'serial_thread'):
            self.serial_thread.stop()
        # Force kill the monitor thread
        self.monitor_thread.terminate()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())