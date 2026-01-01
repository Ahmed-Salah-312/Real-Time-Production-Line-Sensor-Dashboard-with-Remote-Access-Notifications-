import sys
import time
import random
from datetime import datetime

# --- Import psutil for system hardware stats ---
# We wrap this in a try-except block because 'psutil' is not built-in.
# It reads CPU/RAM usage. If missing, the app warns the user and exits.
try:
    import psutil
except ImportError:
    print("CRITICAL: 'psutil' library not found. Please install it using: pip install psutil")
    sys.exit(1)

# PyQt Imports
# Standard imports for creating the Window, Buttons, Tables, and Signals.
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableWidgetItem, QMessageBox,
    QInputDialog, QSystemTrayIcon, QMenu, QHeaderView,
    QVBoxLayout, QPushButton, QDialog, QHBoxLayout, QSizePolicy, QWidget
)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QColor, QIcon

# Matplotlib Imports
# These allow us to embed the data graphs directly into the PyQt window.
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Project Imports
# Import the visual layout file (front.py) and custom dialogs.
from front import Ui_MainWindow
from Dialogs import Set_Password_Dialog, Show_Access_Denied, Show_Access_Granted

# --- CONFIGURATION ---
SENSOR_NAMES = ["Temperature", "Vibration", "Speed", "Pressure", "Optical Counter"]
# Starting points for the simulation (so the graphs don't start at 0)
INITIAL_VALUES = [37.5, 33.0, 78.99, 10.89, 19.0]

# Alarm Logic Dictionary
# Key: Sensor Index (0-4) | Value: (Min Limit, Max Limit)
ALARM_LIMITS = {
    0: (20.0, 45.0),  # Temperature (Alarm if < 20 or > 45)
    1: (0.0, 50.0),  # Vibration
    2: (0.0, 150.0),  # Speed
    3: (5.0, 15.0),  # Pressure
    4: (0.0, 1000.0)  # Optical Counter
}


# --- 1. SENSOR WORKER THREAD ---
# Unlike the Serial version, this creates a SEPARATE thread for every single sensor.
# Each thread runs independently, generating random numbers to mimic a real sensor.
class SensorThread(QThread):
    # This signal sends 3 pieces of data back to the Main Window:
    # 1. sensor_index (Which sensor is this?)
    # 2. current_value (The simulated number)
    # 3. timestamp (When it happened)
    update_signal = pyqtSignal(int, float, str)

    def __init__(self, sensor_index, start_value, interval_sec):
        super().__init__()
        self.sensor_index = sensor_index
        self.start_value = start_value
        self.current_value = start_value
        self.interval = interval_sec  # How fast this sensor updates (e.g., every 0.5s or 1.0s)
        self.is_running = True

    def run(self):
        """The main loop of the simulation thread."""
        while self.is_running:
            # SIMULATION MATH:
            # Generate a random float between -3.0 and +3.0 and add it to the current value.
            # This makes the line on the graph wiggle up and down realistically.
            noise = random.uniform(-3.0, 3.0)
            self.current_value += noise

            # Physics check: values cannot be negative
            if self.current_value < 0: self.current_value = 0

            timestamp = datetime.now().strftime("%H:%M:%S")

            # Send data to GUI
            self.update_signal.emit(self.sensor_index, self.current_value, timestamp)

            # Wait for the specified interval before generating the next point
            time.sleep(self.interval)

    def reset(self):
        """Resets the value back to the starting point (User clicked Restart)."""
        self.current_value = self.start_value

    def stop(self):
        """Safely stops the thread loop."""
        self.is_running = False
        self.wait()


# --- 2. SYSTEM MONITOR THREAD ---
# Monitors the health of the computer running the software (CPU/RAM/HDD).
class SystemMonitorThread(QThread):
    stats_signal = pyqtSignal(str)

    def run(self):
        while True:
            # Get PC Statistics using psutil
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent

            # HDD Temp logic (complex because Windows often blocks this)
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

            # Create formatted HTML string for the log
            msg = (f"<span style='color:blue'><b>[HARDWARE]</b></span> "
                   f"CPU: {cpu}% | RAM: {ram}% | HDD: {hdd_temp}")

            self.stats_signal.emit(msg)
            time.sleep(10)  # Updates every 10 seconds


# --- MAXIMIZE DIALOG ---
# A popup window class used when the user clicks "Maximize" on a graph.
class MaximizeDialog(QDialog):
    def __init__(self, canvas, title, original_layout, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{title} - Maximized View")
        self.resize(900, 600)

        # We temporarily "steal" the canvas from the main window to show it here
        self.canvas = canvas
        self.original_layout = original_layout

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)

    def closeEvent(self, event):
        # IMPORTANT: When closing, give the canvas back to the Main Window
        self.original_layout.addWidget(self.canvas)
        event.accept()


# --- MAIN WINDOW ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Load the UI file (converted from .ui to .py)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # UI Cleanup: Remove 'tab_4' if it exists (placeholder tab)
        if hasattr(self.ui, 'tab_4'):
            index_of_tab_4 = self.ui.tabWidget.indexOf(self.ui.tab_4)
            if index_of_tab_4 != -1:
                self.ui.tabWidget.removeTab(index_of_tab_4)

        # Setup Table: Make columns stretch to fill the width
        self.ui.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ui.tableWidget.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setup_table_items()
        self.setup_system_features()

        # --- BUTTON CONNECTIONS ---
        # Map clicks to functions
        self.ui.Clear_Alarms_Button.clicked.connect(self.clear_alarm_log)
        self.ui.Restart_Simulation_Button.clicked.connect(self.restart_simulation)
        self.ui.Force_Refresh_Button.clicked.connect(self.force_refresh)
        self.ui.Snapshot_of_Values_Button.clicked.connect(self.snapshot_values)
        self.ui.Clear_Alarms_Maintainance_Button.clicked.connect(self.clear_maintenance_log)

        # Initialize Logic Variables
        self.active_alarms = [False] * 5  # Track alarm state for 5 sensors
        self.latest_values = list(INITIAL_VALUES)
        self.update_global_status_label()

        # Setup Plots
        self.views = [
            self.ui.temp_graphicsView,
            self.ui.vibration_graphicsView,
            self.ui.speed_graphicsView,
            self.ui.pressure_graphicsView,
            self.ui.optical_counters_graphicsView
        ]
        self.axes, self.canvases, self.layouts = [], [], []
        self.maximized_windows = []
        self.sensor_histories = [[] for _ in range(5)]  # Store past data for graphing

        # Initialize Matplotlib canvases
        for view, title in zip(self.views, SENSOR_NAMES):
            canvas, ax, layout = self.setup_plot(view, title)
            self.canvases.append(canvas)
            self.axes.append(ax)
            self.layouts.append(layout)

        # --- START SIMULATION THREADS ---
        self.log_system_event("<b>[SYSTEM]</b> Application Started.")
        self.threads = []

        # Define different update speeds for each sensor to make it look realistic
        configs = [
            (0, INITIAL_VALUES[0], 1.0),  # Temp updates every 1.0s
            (1, INITIAL_VALUES[1], 0.5),  # Vibration updates fast (0.5s)
            (2, INITIAL_VALUES[2], 0.8),
            (3, INITIAL_VALUES[3], 1.2),
            (4, INITIAL_VALUES[4], 2.0),
        ]

        # Create 5 separate threads
        for idx, val, interval in configs:
            thread = SensorThread(idx, val, interval)
            # Connect the thread's signal to the main window's update function
            thread.update_signal.connect(self.handle_sensor_update)
            self.threads.append(thread)
            thread.start()

        self.log_system_event(f"<b>[SYSTEM]</b> Started {len(self.threads)} sensor threads successfully.")

        # Start Hardware Monitor
        self.monitor_thread = SystemMonitorThread()
        self.monitor_thread.stats_signal.connect(self.log_system_event)
        self.monitor_thread.start()

    def setup_table_items(self):
        """Fills the table with initial sensor names and values."""
        for i, (name, val) in enumerate(zip(SENSOR_NAMES, INITIAL_VALUES), 1):
            item_name = QTableWidgetItem(name)
            item_name.setTextAlignment(Qt.AlignCenter)
            self.ui.tableWidget.setItem(i, 0, item_name)

            item_val = QTableWidgetItem(str(val))
            item_val.setTextAlignment(Qt.AlignCenter)
            self.ui.tableWidget.setItem(i, 1, item_val)

            self.update_status_gui(i, "OK", QColor("#c8e6c9"))

    def setup_system_features(self):
        """Creates the System Tray Icon and Password Logic."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("../logo2424.png"))
        tray_menu = QMenu()
        tray_menu.addAction("Show").triggered.connect(self.show)
        tray_menu.addAction("Quit").triggered.connect(QApplication.quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        self.maintenance_password = "admin"
        self.last_tab_index = 0
        self.ui.tabWidget.currentChanged.connect(self.check_maintenance_access)

    def setup_plot(self, view, title):
        """Initializes a Matplotlib figure inside a specific UI widget."""
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)

        # Maximize Button
        header = QHBoxLayout()
        header.addStretch()
        btn = QPushButton("Maximize")
        btn.setStyleSheet("font-size: 10px; padding: 2px 8px;")
        header.addWidget(btn)
        layout.addLayout(header)

        # Figure & Canvas
        fig = Figure()
        fig.subplots_adjust(left=0.15, right=0.95, top=0.9, bottom=0.2)
        ax = fig.add_subplot(111)
        ax.grid(True, linestyle='--', alpha=0.5)

        canvas = FigureCanvas(fig)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(canvas)

        btn.clicked.connect(lambda _, c=canvas, t=title, l=layout: self.maximize_plot(c, t, l))
        return canvas, ax, layout

    def maximize_plot(self, canvas, title, layout):
        """Pop out the graph into a larger window."""
        self.log_system_event(f"<b>[UI]</b> User maximized plot: {title}")
        dialog = MaximizeDialog(canvas, title, layout, self)
        dialog.show()
        self.maximized_windows.append(dialog)
        dialog.finished.connect(
            lambda: self.maximized_windows.remove(dialog) if dialog in self.maximized_windows else None)

    # --- CORE SENSOR LOGIC ---
    def handle_sensor_update(self, index, value, timestamp):
        """Called whenever ANY of the 5 sensor threads emits a new value."""
        self.latest_values[index] = value
        row = index + 1

        # 1. Update Table
        item = self.ui.tableWidget.item(row, 1)
        if item: item.setText(f"{value:.2f}")

        item_time = QTableWidgetItem(timestamp)
        item_time.setTextAlignment(Qt.AlignCenter)
        self.ui.tableWidget.setItem(row, 2, item_time)

        # 2. Check Alarms
        self.check_and_log_alarm(index, value, timestamp, row)

        # 3. Update Plots
        current_dt = datetime.now()
        # Add to history list
        self.sensor_histories[index].append((current_dt, value))
        # Keep list size manageable (last 20 points)
        if len(self.sensor_histories[index]) > 20: self.sensor_histories[index].pop(0)

        # Redraw Graph
        times_dt, values = zip(*self.sensor_histories[index])
        times_str = [t.strftime("%S") for t in times_dt]

        ax = self.axes[index]
        ax.cla()
        ax.plot(times_str, values, 'b-', marker='.')
        ax.grid(True, alpha=0.5)
        self.canvases[index].draw()

    def check_and_log_alarm(self, index, value, timestamp, row):
        """Checks if the simulated value is outside safe limits."""
        low_limit, high_limit = ALARM_LIMITS.get(index, (0, 9999))
        sensor_name = SENSOR_NAMES[index]
        alarm_type = None

        if value < low_limit:
            alarm_type = "LOW Limit Triggered"
        elif value > high_limit:
            alarm_type = "HIGH Limit Triggered"

        was_active = self.active_alarms[index]
        is_active = (alarm_type is not None)

        if is_active:
            # --- Alarm Triggered ---
            self.active_alarms[index] = True
            self.update_status_gui(row, "CRITICAL", QColor("#ffcdd2"))
            self.add_alarm_entry(timestamp, sensor_name, value, alarm_type)

            if not was_active:
                # Desktop Notification
                self.tray_icon.showMessage(
                    "CRITICAL ALARM",
                    f"{sensor_name} reached {value:.2f} ({alarm_type})",
                    QSystemTrayIcon.Critical,
                    3000
                )
                self.log_system_event(
                    f"<span style='color:red'><b>[ALARM]</b> {sensor_name} went critical! Value: {value:.2f} ({alarm_type})</span>")

        else:
            # --- Normal State ---
            self.active_alarms[index] = False
            self.update_status_gui(row, "OK", QColor("#c8e6c9"))

            if was_active:
                self.log_system_event(
                    f"<span style='color:green'><b>[RECOVERY]</b> {sensor_name} returned to normal range. Value: {value:.2f}</span>")

        # Update the Main Status Banner (Top of UI)
        self.update_global_status_label()

    def update_global_status_label(self):
        """Updates the top banner based on collective system health."""
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
        """Helper to color the table rows."""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setBackground(color)
        self.ui.tableWidget.setItem(row, 3, item)

    def add_alarm_entry(self, time_str, name, value, alarm_type):
        """Logs alarm details to the text browser."""
        log_entry = (
            f"<span style='color: #555;'>[{time_str}]</span> "
            f"<b>{name}:</b> {value:.2f} — "
            f"<span style='color: red; font-weight: bold;'>{alarm_type}</span>"
        )
        self.ui.Alarm_Log_textBrowser.append(log_entry)
        self.ui.Alarm_Log_textBrowser.moveCursor(self.ui.Alarm_Log_textBrowser.textCursor().End)

    def clear_alarm_log(self):
        self.ui.Alarm_Log_textBrowser.clear()
        self.log_system_event("<b>[USER]</b> Alarm Log cleared by user.")

    def log_system_event(self, message):
        """General logging for user actions and system events."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"<span style='color: #666;'>[{timestamp}]</span> {message}"
        self.ui.Live_Log_Viewer_textBrowser.append(formatted_msg)
        self.ui.Live_Log_Viewer_textBrowser.moveCursor(self.ui.Live_Log_Viewer_textBrowser.textCursor().End)

    def clear_maintenance_log(self):
        self.ui.Live_Log_Viewer_textBrowser.clear()
        self.log_system_event("<b>[USER]</b> Maintenance Logs cleared.")

    def restart_simulation(self):
        """Resets all simulation values to their defaults."""
        self.log_system_event("<b>[ACTION]</b> Simulation Restart requested.")
        for thread in self.threads:
            thread.reset()
        self.sensor_histories = [[] for _ in range(5)]
        # Clear graphs
        for ax, canvas in zip(self.axes, self.canvases):
            ax.cla()
            ax.grid(True, alpha=0.5)
            canvas.draw()
        self.log_system_event("<b>[ACTION]</b> Simulation Restarted & Graphs Cleared.")

    def force_refresh(self):
        """Forces a redraw of all graphs."""
        self.log_system_event("<b>[ACTION]</b> Force Refresh triggered.")
        self.sensor_histories = [[] for _ in range(5)]
        for ax, canvas in zip(self.axes, self.canvases):
            ax.cla()
            ax.grid(True, alpha=0.5)
            canvas.draw()

    def snapshot_values(self):
        """Takes a text 'screenshot' of current values into the log."""
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
        # Delay the check slightly to ensure tab click is registered
        QTimer.singleShot(10, lambda: self._deferred_check(index))

    def _deferred_check(self, index):
        """Handles password protection for the Maintenance tab."""
        if self.ui.tabWidget.tabText(index) == "Maintenance Console":
            self.log_system_event("<b>[SECURITY]</b> Access attempt to Maintenance Console...")
            page = self.ui.tabWidget.widget(index)
            page.setVisible(False)

            # Show password dialog
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

                # If failed/cancelled, switch back to previous tab
                page.setVisible(True)
                self.ui.tabWidget.blockSignals(True)
                self.ui.tabWidget.setCurrentIndex(self.last_tab_index)
                self.ui.tabWidget.blockSignals(False)
        else:
            self.last_tab_index = index

    def closeEvent(self, event):
        """Cleanup when closing the app."""
        self.log_system_event("<b>[SYSTEM]</b> Shutting down application...")
        for t in self.threads: t.stop()
        self.monitor_thread.terminate()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())