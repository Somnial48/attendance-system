# Attendance System (Prezenta)

A modern, QR code-based attendance tracking system designed for educational institutions. This Flask-based web application allows students to mark their attendance using dynamically generated QR codes with built-in location verification and security features.

## Features

### Core Functionality
- 🔐 **Secure QR Code Attendance**: Dynamic QR codes that expire after 10 seconds to prevent fraud
- 📱 **Multi-Device Support**: Students can register their devices and mark attendance from mobile or desktop
- 📍 **GPS Verification**: Optional location-based verification to ensure students are physically present in the classroom
- 🔒 **Session Management**: 40-second attendance sessions with multiple QR code refreshes
- ⏱️ **Cooldown Period**: 2-minute cooldown to prevent duplicate attendance marking

### Admin Panel
- 👥 **Student Management**: Add, edit, and delete student records
- 📊 **Attendance Dashboard**: View and manage attendance records with filtering options
- 📤 **Export Functionality**: Export attendance data in CSV or Excel format
- 📷 **Barcode Scanner**: Alternative attendance marking via barcode scanning
- 🎫 **Registration QR Codes**: Generate QR codes for easy device registration
- ⚙️ **Settings Management**: Configure classrooms, GPS locations, and system parameters

### Security Features
- Password hashing with SHA256
- Token-based authentication
- Device registration with unique tokens
- IP address whitelisting for public networks
- Anti-fraud cooldown mechanisms

## Technology Stack

- **Backend**: Flask (Python web framework)
- **Database**: SQLite3
- **Frontend**: HTML, CSS, JavaScript (vanilla)
- **QR Code Generation**: qrcode library with PIL
- **Web Server**: Gunicorn (production-ready WSGI server)
- **Additional Tools**: OpenCV for barcode scanning

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/Somnial48/attendance-system.git
   cd attendance-system
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the application**
   
   Edit `config.py` to set your preferences:
   - `SECRET_KEY`: Change from default in production
   - `ALLOWED_PUBLIC_IPS`: Add your public IP prefixes
   - `CLASSROOMS`: Configure classroom locations with GPS coordinates
   - `GPS_VERIFICATION_ENABLED`: Enable/disable GPS verification
   - `TOKEN_VALIDITY_SECONDS`: QR code expiration time (default: 10 seconds)

5. **Initialize the database**
   
   The database will be automatically created on first run. The system will create:
   - `data/` directory for database storage
   - Default admin account (username: `admin`, password: `admin`)

6. **Run the application**

   Development mode:
   ```bash
   python start.py
   ```

   Production mode (with Gunicorn):
   ```bash
   ./run.sh
   ```

   The application will be available at `http://127.0.0.1:5000`

## Configuration

### Environment Variables

- `SECRET_KEY`: Flask secret key for session management
- `DEBUG`: Enable/disable debug mode (default: True)

### Classroom Configuration

Edit the `CLASSROOMS` dictionary in `config.py`:

```python
CLASSROOMS = {
    '6-2': {
        'name': '6-2',
        'lat': 47.0617782,      # Latitude
        'lng': 28.8679226,      # Longitude
        'radius_meters': 50     # Acceptable radius in meters
    },
}
```

### IP Whitelisting

Add allowed public IP prefixes in `config.py`:

```python
ALLOWED_PUBLIC_IPS = [
    '192.0.2.',  # Example documentation IP prefix (RFC 5737)
]
```

## Usage

### For Students

1. **Register a Device**
   - Navigate to `/register`
   - Enter your student ID and scan the registration QR code (or enter the token)
   - Allow location access when prompted
   - Your device will be registered for attendance marking

2. **Mark Attendance**
   - Navigate to `/scan` or use the QR code provided by your teacher
   - Scan the displayed QR code
   - Your attendance will be verified and recorded

### For Teachers/Admins

1. **Login**
   - Navigate to `/admin/login`
   - Use the default admin credentials (check system documentation or source code)
   - **Important**: Change the default password immediately after first login for security

2. **Generate QR Codes**
   - Go to "Generate QR Code" in the admin panel
   - Select a classroom
   - QR codes refresh automatically every 10 seconds
   - Students scan these codes to mark attendance

3. **View Attendance**
   - Access the attendance dashboard
   - Filter by date, student, or classroom
   - Export data as needed

4. **Manage Students**
   - Add new students with ID and name
   - Edit or delete existing student records

### Barcode Scanner (Alternative Method)

A standalone barcode scanner utility is provided in `barcode_scanner.py`:

```bash
python barcode_scanner.py
```

This tool uses the device camera to scan student barcodes and can either:
- Verify via API endpoint
- Use local CSV database

## API Endpoints

### Public Endpoints

- `GET /` - Home page
- `GET /register` - Device registration page
- `POST /register` - Submit device registration
- `GET /reregister-device` - Re-register device page
- `GET /verify/qr/<token>` - Verify QR code token
- `GET /scan` - Attendance scanning page
- `POST /api/verify-attendance` - Verify and mark attendance

### Admin Endpoints (Authentication Required)

- `POST /admin/login` - Admin login
- `GET /admin/logout` - Admin logout
- `GET /admin/dashboard` - Admin dashboard
- `GET /admin/generate-qr` - QR code generation page
- `GET /admin/attendance` - Attendance records
- `GET /admin/attendance/export/<format>` - Export attendance (csv/excel)
- `GET /admin/students` - Student management
- `POST /admin/students` - Add new student
- `GET /admin/settings` - System settings
- `GET /admin/scanner` - Barcode scanner page
- `GET /admin/registration-qr` - Registration QR codes

## Project Structure

```
attendance-system/
├── app.py                  # Main Flask application
├── config.py              # Configuration settings
├── database.py            # Database operations
├── start.py               # Development server entry point
├── run.sh                 # Production server script
├── barcode_scanner.py     # Barcode scanning utility
├── reset_password.py      # Password reset utility
├── requirements.txt       # Python dependencies
├── nginx.conf            # Nginx configuration (for deployment)
├── data/                 # Database and data storage
├── templates/            # HTML templates
│   ├── index.html
│   ├── register.html
│   ├── scan.html
│   ├── verify_qr.html
│   └── admin/           # Admin panel templates
└── static/              # Static assets (CSS, JS, images)
```

## Security Considerations

1. **Change Default Credentials**: The system creates a default admin account. Change the password immediately after installation.

2. **Secret Key**: Update the `SECRET_KEY` in production to a strong, random value.

3. **HTTPS**: For production deployment, always use HTTPS to protect tokens and passwords in transit.

4. **GPS Verification**: Enable GPS verification to ensure students are physically present in the classroom.

5. **IP Whitelisting**: Configure allowed IP ranges to restrict attendance marking to specific networks.

## Troubleshooting

### Database Issues
- If the database becomes corrupted, delete the `data/attendance.db` file and restart the application to reinitialize.

### QR Code Not Working
- Ensure the system clock is synchronized (QR codes are time-sensitive)
- Check that GPS location access is granted
- Verify you're within the configured classroom radius

### Admin Login Issues
- Use the password reset utility: `python reset_password.py`

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is provided as-is for educational purposes. Please ensure compliance with your institution's policies when using this system.

## Support

For issues, questions, or contributions, please open an issue on GitHub or contact the repository maintainer.
