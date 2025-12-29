"""
Cofiguratie pentru sistemul de prezenta al universitatii.
"""

import os

# Cofiguratie flask
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

# Fisierer
DATA_DIR = 'data'
DATABASE_DIR = 'Database'
DATABASE_FILE = os.path.join(DATA_DIR, 'attendance.db')


TOKEN_VALIDITY_SECONDS = 10  # Fiecare Qr code este valid pentru 10 secunde
QR_TOKEN_BUFFER_SECONDS = 7  # Buffer mai mult pentru validarea QR tokenului
SESSION_DURATION_SECONDS = 40  # Durata totala a sesiunii: 4 Qr code x 10 secunde
DEVICE_REREGISTER_COOLDOWN_SECONDS = 120  # 2 minute de asteptare dupa marcarea prezentei


# Ip prefixe publice permise pentru marcarea prezentei
ALLOWED_PUBLIC_IPS = [  # Retea locala for me
    '81.180.', #EXEMPLU 
]

# Locatia claseii
# Format: {'classroom_name': {'name': name, 'lat': latitude, 'lng': longitude, 'radius_meters': meters}}
CLASSROOMS = {
    '6-2': {
        'name': '6-2',
        'lat': 47.0617782,
        'lng': 28.8679226,
        'radius_meters': 50
    },
}

# Activare verificare GPS
GPS_VERIFICATION_ENABLED = True
