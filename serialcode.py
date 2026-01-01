import serial
import sys

# --- CONFIGURATION ---
SERIAL_PORT = 'COM8'  # Adjust as needed
SERIAL_RATE = 115200


def Read_From_Serial():
    ser = None
    try:
        # Open serial port
        ser = serial.Serial(SERIAL_PORT, SERIAL_RATE, timeout=1)
        print(f"STATUS: Connected to {SERIAL_PORT} at {SERIAL_RATE} baud.")
        print("PROTOCOL: Expecting format 'Temp,Vib,Speed,Press,Count,Time'")
        print("-" * 50)

        while True:
            if ser.in_waiting > 0:
                # 1. READ (ASCII Protocol)
                # Read line until \n, decode to string, strip whitespace
                raw_data = ser.readline().decode('utf-8', errors='ignore').strip()

                # 2. PARSE (Split by delimiter)
                # We expect 6 values separated by commas
                parts = raw_data.split(',')

                # 3. VALIDATE (Check Protocol Integrity)
                if len(parts) == 6:
                    try:
                        # Extract data
                        temp = float(parts[0])
                        vib = float(parts[1])
                        speed = float(parts[2])
                        press = float(parts[3])
                        count = float(parts[4])
                        timestamp = parts[5]

                        # Success: We successfully implemented the protocol
                        print(f"[VALID PACKET] Time: {timestamp} | "
                              f"T:{temp} V:{vib} S:{speed} P:{press} C:{count}")

                    except ValueError:
                        print(f"[ERROR] Data corruption (Conversion failed): {raw_data}")
                else:
                    # Packet didn't match the protocol length
                    if raw_data:  # Ignore empty lines
                        print(f"[INVALID PACKET] Structure mismatch: {raw_data}")

    except serial.SerialException as e:
        print(f"CRITICAL: Could not open serial port {SERIAL_PORT}.")
        print(f"Reason: {e}")

    except KeyboardInterrupt:
        print("\nSTATUS: User stopped the script.")

    finally:
        if ser and ser.is_open:
            ser.close()
            print("STATUS: Serial port closed.")


if __name__ == "__main__":
    Read_From_Serial()