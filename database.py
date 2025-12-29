""" 
Un Modul pentru aplicatia principala cu toate functiile, aici e asa un futai
"""

import sqlite3
import os
import hashlib
from contextlib import contextmanager
from datetime import datetime
import config


DATABASE_PATH = os.path.join(config.DATA_DIR, 'attendance.db')

def _hash_password(password):
    """Hash a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection():
    # Se face conexiunea la baza de date
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

@contextmanager
def db_connection():
    # Se gestioneaza conexiunea la baza de date, BLEAAAA
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_database():
    # Se initializeaza baza de date cu toate tabelele.
    # Verificam daca baza de date exista inainte de initializare
    is_new_database = not os.path.exists(DATABASE_PATH)
    
    with db_connection() as conn:
        cursor = conn.cursor()
        
        # Student table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                group_name TEXT NOT NULL,
                barcode_hash TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_students_group ON students(group_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_students_barcode ON students(barcode_hash)')
        
        # Devices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                student_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL,
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_agent TEXT,
                device_type TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_token ON devices(token_hash)')
        
        # Migrare: adaugam coloanele user_agent si device_type daca nu exista
        cursor.execute("PRAGMA table_info(devices)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'user_agent' not in columns:
            cursor.execute('ALTER TABLE devices ADD COLUMN user_agent TEXT')
        if 'device_type' not in columns:
            cursor.execute('ALTER TABLE devices ADD COLUMN device_type TEXT')
        
        # Attendance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_lesson ON attendance(lesson_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date(timestamp))')
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_unique ON attendance(student_id, lesson_id)')
        
        # Pentru profesori
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teachers (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT DEFAULT 'teacher',
                password_changed INTEGER DEFAULT 0
            )
        ''')
        
        # Cool down la dispozitive
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_cooldowns (
                token_hash TEXT PRIMARY KEY,
                last_action DATETIME NOT NULL
            )
        ''')
        
        # QR tokens table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS qr_tokens (
                token TEXT PRIMARY KEY,
                lesson_id TEXT NOT NULL,
                classroom TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        ''')
        
        # Daca baza de date e noua, cream utilizatorul admin default
        if is_new_database:
            default_username = 'admin'
            default_password = 'admin123'
            default_display_name = 'Administrator'
            default_role = 'admin'
            password_hash = _hash_password(default_password)
            
            cursor.execute('''
                INSERT OR IGNORE INTO teachers (username, password_hash, display_name, role, password_changed)
                VALUES (?, ?, ?, ?, ?)
            ''', (default_username, password_hash, default_display_name, default_role, 0))
            print(f"Baza de date noua creata. Utilizator admin default: '{default_username}' cu parola: '{default_password}'")


#Operatii pe studenti, dispozitive, prezenta, profesori, cooldown-uri, tokenuri QR

def db_read_students():
    # Citieste toti studentii din baza de date
    students = {}
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, surname, group_name, barcode_hash, created_at FROM students')
        for row in cursor.fetchall():
            students[row['id']] = {
                'name': row['name'],
                'surname': row['surname'],
                'group': row['group_name'],
                'barcode': row['barcode_hash'] or '',
                'timestamp': row['created_at'] or ''
            }
    return students

def db_write_student(student_id, name, surname, group, barcode='', timestamp=None):
    # Adauga sau modifica un student
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO students (id, name, surname, group_name, barcode_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, name, surname, group, barcode, timestamp))

def db_delete_student(student_id):
    # Se sterge un student
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM students WHERE id = ?', (student_id,))


# Operatii pe dispozitive

def db_read_devices():
    # Se citesc toate device-urile
    devices = {}
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT student_id, token_hash, registered_at, user_agent, device_type FROM devices')
        for row in cursor.fetchall():
            devices[row['student_id']] = {
                'token_hash': row['token_hash'],
                'registered_at': row['registered_at'] or '',
                'user_agent': row['user_agent'] or '',
                'device_type': row['device_type'] or 'unknown'
            }
    return devices

def db_write_device(student_id, token_hash, registered_at=None, user_agent=None, device_type=None):
    # Se adauga sau modifica un device
    # IMPORTANT: Mai intai se sterge orice alt student care are acelasi token_hash
    # (un device poate fi inregistrat doar pentru un singur student la un moment dat)
    if registered_at is None:
        registered_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with db_connection() as conn:
        cursor = conn.cursor()
        # Se sterg toate inregistrarile de device cu acelasi token (alt student cu acelasi telefon)
        cursor.execute('DELETE FROM devices WHERE token_hash = ? AND student_id != ?', (token_hash, student_id))
        cursor.execute('''
            INSERT OR REPLACE INTO devices (student_id, token_hash, registered_at, user_agent, device_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (student_id, token_hash, registered_at, user_agent, device_type))

def db_delete_device(student_id):
    # Se sterge un device
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM devices WHERE student_id = ?', (student_id,))

def db_find_student_by_token(token_hash):
    # Se gaseste studentul dupa tokenul device-ului
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT student_id FROM devices WHERE token_hash = ?', (token_hash,))
        row = cursor.fetchone()
        return row['student_id'] if row else None


# Operatii pe prezenta

def db_read_attendance():
    # Se citesc toate inregistrarile de prezenta
    attendance = []
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT student_id, lesson_id, timestamp FROM attendance ORDER BY timestamp')
        for row in cursor.fetchall():
            attendance.append({
                'barcode_hash': row['student_id'],
                'lesson_id': row['lesson_id'],
                'timestamp': row['timestamp']
            })
    return attendance

def db_write_attendance(student_id, lesson_id, timestamp=None):
    # Se adauga prezenta.
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO attendance (student_id, lesson_id, timestamp)
                VALUES (?, ?, ?)
            ''', (student_id, lesson_id, timestamp))
            return True
        except sqlite3.IntegrityError:
            # daca sunt duplicate (studentul a fost deja marcat prezent)
            return False

def db_check_attendance_exists(student_id, lesson_id):
    # Se verifica daca prezenta exista deja
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 1 FROM attendance WHERE student_id = ? AND lesson_id = ?
        ''', (student_id, lesson_id))
        return cursor.fetchone() is not None

def db_delete_attendance(student_id, lesson_id):
    # Se sterge prezenta pentru un student si o lectie
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM attendance WHERE student_id = ? AND lesson_id = ?
        ''', (student_id, lesson_id))
        return cursor.rowcount > 0


# Profesorii operatii

def db_read_teachers():
    # Se citesc toti profesorii din baza de date
    teachers = {}
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT username, password_hash, display_name, role, password_changed FROM teachers')
        for row in cursor.fetchall():
            teachers[row['username']] = {
                'password_hash': row['password_hash'],
                'display_name': row['display_name'],
                'role': row['role'],
                'password_changed': bool(row['password_changed'])
            }
    return teachers

def db_write_teacher(username, password_hash, display_name, role='teacher', password_changed=False):
    # Se adauga sau modifica un profesor, asta in caz de facem penteru productie
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO teachers (username, password_hash, display_name, role, password_changed)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, password_hash, display_name, role, 1 if password_changed else 0))

def db_update_teacher_password(username, new_password_hash):
    # Se actualizeaza parola profesorului si se marcheaza ca schimbata
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE teachers SET password_hash = ?, password_changed = 1 WHERE username = ?
        ''', (new_password_hash, username))
        return cursor.rowcount > 0


# Coolfown-uri la dispozitive

def db_read_device_cooldowns():
    # Se citesc toate cooldown-urile dispozitivelor
    cooldowns = {}
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT token_hash, last_action FROM device_cooldowns')
        for row in cursor.fetchall():
            cooldowns[row['token_hash']] = row['last_action']
    return cooldowns

def db_write_device_cooldown(token_hash, last_action=None):
    # Se adauga sau modifica un cooldown pentru un device
    if last_action is None:
        last_action = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO device_cooldowns (token_hash, last_action)
            VALUES (?, ?)
        ''', (token_hash, last_action))

def db_cleanup_device_cooldowns(cooldown_seconds):
    # Se sterg cooldown-urile expirate
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM device_cooldowns 
            WHERE datetime(last_action, '+' || ? || ' seconds') < datetime('now')
        ''', (cooldown_seconds,))


# Operatii pe token-urile QR

def db_read_qr_tokens():
    # Se citesc toate token-urile QR
    tokens = {}
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT token, lesson_id, classroom, created_at FROM qr_tokens')
        for row in cursor.fetchall():
            tokens[row['token']] = {
                'lesson_id': row['lesson_id'],
                'classroom': row['classroom'],
                'created_at': row['created_at']
            }
    return tokens

def db_write_qr_token(token, lesson_id, classroom, created_at):
    # Se adauga sau modifica un token QR
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO qr_tokens (token, lesson_id, classroom, created_at)
            VALUES (?, ?, ?, ?)
        ''', (token, lesson_id, classroom, created_at))

def db_delete_qr_token(token):
    # Se sterge un token QR
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM qr_tokens WHERE token = ?', (token,))

def db_cleanup_qr_tokens(validity_seconds):
    # Se sterg token-urile QR expirate
    import time
    cutoff = time.time() - validity_seconds
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM qr_tokens WHERE created_at < ?', (cutoff,))


# Se intializeza baza de date la importarea modulului ,cat chin a fost AICI
init_database()
