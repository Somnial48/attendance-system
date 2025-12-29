"""
Barcode Scanner for Attendance System
Uses OpenCV to scan barcodes from camera and log attendance
"""

import cv2
import pandas as pd
from datetime import datetime
import os
import requests

# ------------------ CONFIGURATION ------------------
API_URL = "http://localhost:5000/api/verify-attendance"  # Change to your server URL
USE_API = False  # Set to True to verify via API instead of local CSV

# ------------------ LOAD STUDENT DATABASE ------------------
db_file = "data/students.txt"
students = {}

if os.path.exists(db_file):
    with open(db_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            if "=" in line:
                # Legacy format
                code, name = line.split("=", 1)
                students[code.strip()] = name.strip()
            elif "|" in line:
                # New format: Name|Surname|Group|Barcode|Timestamp
                parts = line.split("|")
                if len(parts) >= 4:
                    code = parts[3]
                    name = f"{parts[0]} {parts[1]}"
                    students[code] = name
else:
    print("WARNING: students.txt not found — codes will be saved without names.")

# ------------------ LOAD/CREATE ATTENDANCE CSV ------------------
attendance_file = "attendance.csv"

try:
    df = pd.read_csv(attendance_file)
except:
    df = pd.DataFrame(columns=["Barcode", "Name", "Timestamp"])
    df.to_csv(attendance_file, index=False)

# ------------------ OPENCV BARCODE SCANNER ------------------
detector = cv2.barcode.BarcodeDetector()

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
print("Camera started. Press Q to quit. Press M for manual entry.")

scanned = set()

def mark_attendance(code):
    """Save attendance record to CSV or API"""
    name = students.get(code, "Unknown Student")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if USE_API:
        # TODO: Implement API verification
        # This would require QR token, device token, and GPS coordinates
        print(f"[!] API mode not fully implemented. Use local CSV mode.")
        print(f"[+] Would verify: {code} - {name}")
    else:
        # Local CSV mode
        print(f"[+] Marked present: {code} - {name} at {timestamp}")
        
        global df
        new_row = pd.DataFrame([[code, name, timestamp]], columns=df.columns)
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(attendance_file, index=False)

# ------------------ MAIN LOOP ------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    ok, decoded_info, decoded_type, points = detector.detectAndDecodeWithType(frame)

    if ok and decoded_info:
        if isinstance(decoded_info, tuple):
            code = str(decoded_info[0]).strip() if decoded_info else ""
        else:
            code = str(decoded_info).strip()
        
        if code and code not in scanned:
            scanned.add(code)
            mark_attendance(code)

        if points is not None and len(points) > 0:
            pts = points[0].astype(int).reshape(-1, 2)
            for i in range(len(pts)):
                cv2.line(frame, tuple(pts[i]), tuple(pts[(i+1) % len(pts)]), (0, 255, 0), 2)

    cv2.putText(frame, "Press Q to quit | Press M for manual entry",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, "Scanning...", 
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow("Attendance Scanner", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break

    if key == ord('m'):
        cap.release()
        cv2.destroyAllWindows()
        code = input("Introdu barcodul manual ").strip()
        mark_attendance(code)
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

cap.release()
cv2.destroyAllWindows()
print("\n[✓] Scanner closed. Attendance saved to", attendance_file)
