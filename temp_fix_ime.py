import serial
import time

port = "COM1"
baudrate = 115200

try:
    ser = serial.Serial(port, baudrate, timeout=2)
    print("Connected to COM1")
    time.sleep(0.5)
    
    ser.write(b'\n')
    time.sleep(0.5)
    
    cmd = 'settings put secure default_input_method com.android.inputmethod.latin/.LatinIME\n'
    ser.write(cmd.encode('utf-8'))
    print("Command sent")
    time.sleep(1)
    
    if ser.in_waiting:
        response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        print("Response:", response)
    
    ser.close()
except Exception as e:
    print("Error:", str(e))
