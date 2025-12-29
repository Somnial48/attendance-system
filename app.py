""" 
Prezenta - Main Flask app
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response, make_response
import hashlib
import csv
import secrets
import time
import os
import json
from datetime import datetime
import qrcode
import io
import base64
from math import radians, cos, sin, asin, sqrt

import config
from database import (
    db_read_students, db_write_student, db_delete_student,
    db_read_devices, db_write_device, db_delete_device, db_find_student_by_token,
    db_read_attendance, db_write_attendance, db_check_attendance_exists, db_delete_attendance,
    db_read_teachers, db_write_teacher, db_update_teacher_password,
    db_read_device_cooldowns, db_write_device_cooldown, db_cleanup_device_cooldowns,
    db_read_qr_tokens, db_write_qr_token, db_cleanup_qr_tokens
)

app = Flask(__name__)
app.config.from_object(config)
app.debug = True  #
FLASK_DEBUG=1
# vedem daca exista folderul
os.makedirs(config.DATA_DIR, exist_ok=True)

# Fucntiile maine pentru tot

def hash_token(token):
    # Hash la tokenul de device
    return hashlib.sha256(token.encode()).hexdigest()

def hash_password(password):
    # Hash la parola folosind SHA256
    return hashlib.sha256(password.encode()).hexdigest()

def hash_barcode(barcode):
    # Hash barcode pentru cei care zic ca e privat
    return hashlib.sha256(barcode.encode()).hexdigest()

def detect_device_type(user_agent):
    # Se verifica daca e mobil sau computer din User-Agent
    if not user_agent:
        return 'unknown'
    
    ua_lower = user_agent.lower()
    
    # Keywords pentru mobile, samsung e al meu
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'ipod', 'blackberry', 
                       'windows phone', 'opera mini', 'opera mobi', 'webos', 'palm',
                       'symbian', 'nokia', 'samsung', 'lg-', 'htc', 'mot-', 'huawei']
    
    # Pentru tablete
    tablet_keywords = ['tablet', 'ipad', 'playbook', 'silk']
    
    # Le comanseci in una, sa fie mai simplu
    for keyword in mobile_keywords + tablet_keywords:
        if keyword in ua_lower:
            return 'mobile'
    
    # Sa vedem cine e la calculator
    desktop_keywords = ['windows nt', 'macintosh', 'mac os x', 'linux x86', 'linux i686', 'linux amd64']
    for keyword in desktop_keywords:
        if keyword in ua_lower:
            # Inca o verificare sa nu fie mobil
            if 'mobile' not in ua_lower and 'android' not in ua_lower:
                return 'computer'
    
    return 'unknown'

def generate_student_id(name, surname, group):
    # Generarea un nou hash bazat pe nume, prenume si grupa
    identifier = f"{name.lower().strip()}|{surname.lower().strip()}|{group.upper().strip()}"
    return hashlib.sha256(identifier.encode()).hexdigest()

def generate_device_token():
    # generarea tokenului de device
    return secrets.token_urlsafe(32)

def generate_qr_token():
    # Generarea unui token QR unic
    return secrets.token_urlsafe(32)


# Fucntiile pentru baza de date,               ia ibu sa stricat tot

def read_students():
    # Citeste toti studentii din baza de date
    return db_read_students()

def write_students(students):
    # Scrie toti studentii, cu toate infromatiile deja tot gata
    for student_id, student in students.items():
        db_write_student(
            student_id,
            student['name'],
            student['surname'],
            student['group'],
            student.get('barcode', ''),
            student.get('timestamp', '')
        )

def add_student(name, surname, group, barcode=''):
    # Adauga un student nou
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    student_id = generate_student_id(name, surname, group)
    barcode_hash = hash_barcode(barcode) if barcode else ''
    db_write_student(student_id, name, surname, group, barcode_hash, timestamp)
    return student_id

def read_devices():
    # Citeste toate device-urile din baza de date
    return db_read_devices()

def write_devices(devices):
    # Scrie toate device-urile, tot gata, in bloc
    for student_id, data in devices.items():
        if isinstance(data, dict):
            db_write_device(student_id, data.get('token_hash', ''), data.get('registered_at', ''))
        else:
            db_write_device(student_id, data, '')

def read_device_cooldowns():
    # Se citeste cooldwown-urile de device
    return db_read_device_cooldowns()

def write_device_cooldowns(cooldowns):
    # Scrie cooldown-urile de device, dupa ce se scaneasza
    for token_hash, timestamp in cooldowns.items():
        db_write_device_cooldown(token_hash, timestamp)

def read_teachers():
    # Citeste toti profesorii din baza de date
    return db_read_teachers()

def write_teachers(teachers):
    # Scrie toti profesorii, daca or mai fi cineva
    for username, teacher in teachers.items():
        db_write_teacher(
            username,
            teacher['password_hash'],
            teacher['display_name'],
            teacher.get('role', 'teacher'),
            teacher.get('password_changed', False)
        )

def update_teacher_password(username, new_password):
    # Schimba parola profesorului
    return db_update_teacher_password(username, hash_password(new_password))

def read_attendance():
    # Citeste prezentele din baza de date
    return db_read_attendance()

def write_attendance_by_student_id(student_id, lesson_id):
    # Scrie prezenta folosind student_id
    db_write_attendance(student_id, lesson_id)

def write_attendance(barcode, lesson_id):
    # Scrie prezenta (legacy - pentru scanner), un pupic Danu
    barcode_hash = hash_barcode(barcode)
    db_write_attendance(barcode_hash, lesson_id)

def read_qr_tokens():
    # Citeste tokenurile QR din baza de date
    return db_read_qr_tokens()

def write_qr_tokens(tokens):
    # Scrie tokenurile QR
    for token, data in tokens.items():
        db_write_qr_token(token, data['lesson_id'], data['classroom'], data['created_at'])

def add_qr_token(token, lesson_id, classroom):
    # Adauga un token QR nou
    created_at = time.time()
    db_write_qr_token(token, lesson_id, classroom, created_at)
    return {
        'lesson_id': lesson_id,
        'classroom': classroom,
        'created_at': created_at
    }

def haversine_distance(lat1, lon1, lat2, lon2):
    # Calculeaza distanta in metri intre doua puncte GPS folosind formula Haversine
    # Se convertesc gradele in radiani
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Raza Pamantului la putere!!!
    return c * r


# Format QR: {token: {'lesson_id': str, 'classroom': str, 'created_at': float}}
active_qr_tokens = {}
# mapeaza QRCODE cu  codul cela de la QRcode prezenta
display_code_to_token = {}

# Rutele Principale pe website

@app.route('/')
def index():
    # Pagina principala
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Inregistrarea studentului
    if request.method == 'POST':
        data = request.json
        name = data.get('name', '').strip()
        surname = data.get('surname', '').strip()
        group = data.get('group', '').strip()
        barcode = data.get('barcode', '').strip()  # Optional now
        device_token = data.get('device_token', '').strip()
        
        # Se valideaza inputurile (barcode is now optional)
        if not all([name, surname, group, device_token]):
            return jsonify({'success': False, 'error': 'Numele, prenumele si grupa trebuie sa fie completate'}), 400
        
        # se valideaza sa nu fie pipe
        if any('|' in field for field in [name, surname, group]):
            return jsonify({'success': False, 'error': 'Nu popate contine |'}), 400
        
        # Validare la barcode
        if barcode and (len(barcode) != 8 or not barcode.isdigit()):
            return jsonify({'success': False, 'error': 'Barcode trebuie sa aipa 8 cifre'}), 400
        
        # Se verifica cooldown-ul pe dispozitiv (sa nu se poata inregistra alt student rapid)
        device_token_hash = hash_token(device_token)
        cooldowns = read_device_cooldowns()
        
        if device_token_hash in cooldowns:
            try:
                last_action = datetime.strptime(cooldowns[device_token_hash], '%Y-%m-%d %H:%M:%S')
                time_since_last = (datetime.now() - last_action).total_seconds()
                cooldown_remaining = config.DEVICE_REREGISTER_COOLDOWN_SECONDS - time_since_last
                
                if cooldown_remaining > 0:
                    minutes_remaining = int(cooldown_remaining // 60)
                    seconds_remaining = int(cooldown_remaining % 60)
                    return jsonify({
                        'success': False, 
                        'error': f'Posibil ca o faci pe Desteptul. Acest dispozitiv trebuie sa astepte {minutes_remaining} minute si {seconds_remaining} secunde inainte de a inregistra alt student.'
                    }), 400
            except ValueError:
                pass  # error handling, ignora si ii da mai departe
        
        # CSe vericica sa nu fie deja student existent
        students = read_students()
        student_id = generate_student_id(name, surname, group)
        if student_id in students:
            return jsonify({'success': False, 'error': 'Acest student este deja inregistrat'}), 400
        
        # Se adauga studentul
        student_id = add_student(name, surname, group, barcode)
        
        # Se reia informatiile despre device
        user_agent = request.headers.get('User-Agent', '')
        device_type = detect_device_type(user_agent)
        
        # Se inregistreaza tokenul dispozitivului cu informatiile despre device
        db_write_device(student_id, hash_token(device_token), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_agent, device_type)
        
        return jsonify({'success': True, 'message': 'Te-ai inregistrat cu succes', 'student_id': student_id})
    
    return render_template('register.html')

@app.route('/reregister-device', methods=['GET', 'POST'])
def reregister_device():
    # Reinregistrarea dispozitivului pentru un student existent
    if request.method == 'POST':
        data = request.json
        name = data.get('name', '').strip()
        surname = data.get('surname', '').strip()
        group = data.get('group', '').strip()
        confirmation_code = data.get('confirmation_code', '').strip()
        existing_device_token = data.get('existing_device_token', '').strip()
        
        # Validarea inputurilor
        if not all([name, surname, group, confirmation_code]):
            return jsonify({'success': False, 'error': 'Toate trebuie sa fie completate'}), 400
        
        # verificare student existent
        students = read_students()
        student_id = generate_student_id(name, surname, group)
        if student_id not in students:
            return jsonify({'success': False, 'error': 'Student nu exista'}), 400
        
        # Se verifica codul de confirmare (Grupa + Prima litera a Numelui)
        student = students[student_id]
        expected_code = student['group'] + student['name'][0].upper()
        
        if confirmation_code.upper() != expected_code.upper():
            return jsonify({'success': False, 'error': 'Cod de confirmare invalid'}), 400
        
        # Se verifica cooldown-ul pe dispozitivul existent
        # Asta ii opreste pe toti desteptii sa schimbe device-ul rapid ca sa isi marcheze prezenta
        if existing_device_token:
            existing_token_hash = hash_token(existing_device_token)
            cooldowns = read_device_cooldowns()
            
            if existing_token_hash in cooldowns:
                try:
                    last_action = datetime.strptime(cooldowns[existing_token_hash], '%Y-%m-%d %H:%M:%S')
                    time_since_last = (datetime.now() - last_action).total_seconds()
                    cooldown_remaining = config.DEVICE_REREGISTER_COOLDOWN_SECONDS - time_since_last
                    
                    if cooldown_remaining > 0:
                        minutes_remaining = int(cooldown_remaining // 60)
                        seconds_remaining = int(cooldown_remaining % 60)
                        return jsonify({
                            'success': False, 
                            'error': f'Posibil ca o faci pe Desteptul. Acest dispozitiv trebuie sa astepte {minutes_remaining} minute si {seconds_remaining} secunde inainte de a face alta schimbare.'
                        }), 400
                except ValueError:
                    pass  # error handling, ignore and proceed
        
        # Se genereaza un nou token de device pe server
        new_device_token = generate_device_token()
        new_token_hash = hash_token(new_device_token)
        
        # Se reiau informatiile despre device
        user_agent = request.headers.get('User-Agent', '')
        device_type = detect_device_type(user_agent)
        
        # Se actualizeaza tokenul dispozitivului cu informatiile despre device
        db_write_device(student_id, new_token_hash, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_agent, device_type)

        return jsonify({
            'success': True, 
            'message': 'Ai reinregistrat dispozitivul cu succes',
            'new_device_token': new_device_token  # Se trimite noul token inapoi la telefon
        })
    
    return render_template('reregister.html')

@app.route('/verify/qr/<token>')
def verify_qr(token):
    # Pagina de verificare a codului QR
    return render_template('verify_qr.html', token=token)

#


@app.route('/scan')
def student_scan():
    # Pagina pentru studenti pentru a scana codul QR
    return render_template(
        'scan.html',
        qr_token_buffer_seconds=config.QR_TOKEN_BUFFER_SECONDS,
        token_validity_seconds=config.TOKEN_VALIDITY_SECONDS
    )

@app.route('/api/verify-attendance', methods=['POST'])
def verify_attendance():
    # Verifica prezenta pentru un student
    # 1. QR Token Valid
    # 2. Student Exista (de token)
    # 3. Fara duplicari
    # 4. GPS Location Obligatoriu + Verificare IP
    data = request.json
    qr_token = data.get('qr_token', '').strip()
    device_token = data.get('device_token', '').strip()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    # Luam IP-ul clientului
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()

    # verificam QR codul token valid - se uita baza de date
    all_tokens = read_qr_tokens()
    # Vedem tokenurile
    print('DEBUG: Available QR tokens:', list(all_tokens.keys()))
    print('DEBUG: Received qr_token:', repr(qr_token))
    # Se incearca sa se potriveasca tokenul exact, sau cu whitespace eliminat
    token_match = qr_token
    if qr_token not in all_tokens:
        qr_token_stripped = qr_token.strip()
        if qr_token_stripped in all_tokens:
            token_match = qr_token_stripped
        elif qr_token in display_code_to_token:
            mapped_token = display_code_to_token[qr_token]
            if mapped_token in all_tokens:
                token_match = mapped_token
            else:
                return jsonify({'success': False, 'error': 'Cod QR invalid sau expirat. Scanati un cod QR nou de la profesor:(.'}), 400
        else:
            return jsonify({'success': False, 'error': 'Cod QR invalid sau expirat. Scanati un cod QR nou de la profesor:(.'}), 400
    qr_data = all_tokens[token_match]
    token_age = time.time() - qr_data['created_at']
    
    # Se da un timp pentru GPS (+buffer din config)
    if token_age > (config.TOKEN_VALIDITY_SECONDS + config.QR_TOKEN_BUFFER_SECONDS):
        return jsonify({'success': False, 'error': 'Cod QR expirat. Scanati un cod QR nou de la profesor:(.'}), 400
    
    lesson_id = qr_data['lesson_id']
    classroom = qr_data['classroom']

    # Se cauta studentul dupa tokenul dispozitivului
    devices = read_devices()
    student_id = None
    device_token_hash = hash_token(device_token)
    
    for sid, device_data in devices.items():
        # se verifica tokenulz si ca string si dict
        stored_hash = device_data.get('token_hash') if isinstance(device_data, dict) else device_data
        if stored_hash == device_token_hash:
            student_id = sid
            break
    
    if not student_id:
        return jsonify({'success': False, 'error': 'Device-ul nu este inregistrat. Inregistreaza-te prima data.'}), 400
    
    # Se verifica daca studentul exista
    students = read_students()
    if student_id not in students:
        return jsonify({'success': False, 'error': 'Student nu exista in sistem, vezi daca esti inregistrat.'}), 400
    
    student = students[student_id]

    # Fara duplicari
    attendance = read_attendance()
    for record in attendance:
        if record['barcode_hash'] == student_id and record['lesson_id'] == lesson_id:
            return jsonify({'success': False, 'error': 'Deja ti-ai facut prezenta aici'}), 400
    
    # GPS Location este OBLIGATORIU la pidari
    location_valid = False
    ip_valid = False
    
    # Verificare IP - debug logging
    print(f"[DEBUG] Client IP detected: '{client_ip}'")
    print(f"[DEBUG] Allowed prefixes: {config.ALLOWED_PUBLIC_IPS}")
    
    for allowed_prefix in config.ALLOWED_PUBLIC_IPS:
        print(f"[DEBUG] Checking if '{client_ip}' starts with '{allowed_prefix}': {client_ip.startswith(allowed_prefix)}")
        if client_ip.startswith(allowed_prefix):
            ip_valid = True
            print(f"[DEBUG] IP match found with prefix: {allowed_prefix}")
            break
    
    if not ip_valid:
        print(f"[DEBUG] IP verification failed for: {client_ip}")
        return jsonify({
            'success': False, 
            'error': f'IP-ul tau ({client_ip}) nu este permis pentru marcarea prezentei. Conecteaza-te la reteaua universitatii, hai gazul.'
        }), 400
    # Se verifica locatia GPS
    if latitude is None or longitude is None:
        return jsonify({
            'success': False, 
            'error': 'GPS este OBLIGATORIE!!!!. Activeaza locatia si incearca din nou:)'
        }), 400
    
    if classroom in config.CLASSROOMS:
        classroom_data = config.CLASSROOMS[classroom]
        distance = haversine_distance(
            latitude, longitude,
            classroom_data['lat'], classroom_data['lng']
        )
        if distance <= classroom_data['radius_meters']:
            location_valid = True
    
    if not location_valid:
        return jsonify({
            'success': False, 
            'error': 'Trebuie sa fii in clasa pentru a marca prezenta. Verifica GPS-ul.'
        }), 400
    
    # Daca tot bine, se scrie prezenta
    write_attendance_by_student_id(student_id, lesson_id)
    
    # Se actualizeaza cooldown-ul dispozitivului
    # Sa ii oprim pe pidarii care schimba device-ul rapid
    cooldowns = read_device_cooldowns()
    cooldowns[device_token_hash] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    write_device_cooldowns(cooldowns)
    
    return jsonify({
        'success': True,
        'message': f'Prezenta sa facut cu succes pentru {student["surname"]} {student["name"]}, super:)'
    })

# Acuma avem rutele pentru admin, bleeaaaaaaaaa

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # Login pentru profesori
    if request.method == 'POST':
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        teachers = read_teachers()
        if username in teachers:
            teacher = teachers[username]
            if hash_password(password) == teacher['password_hash']:
                session['logged_in'] = True
                session['username'] = username
                session['display_name'] = teacher['display_name']
                session['password_changed'] = teacher.get('password_changed', False)
                return jsonify({'success': True})

        return jsonify({'success': False, 'error': 'Credentiale invalide, mai incearca'}), 401

    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    # Logout pentru profesori, pa pa
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/api/admin/check-default-password')
def check_default_password():
    # Verifica daca un profesor foloseste parola default
    teachers = read_teachers()
    for username, teacher in teachers.items():
        if not teacher.get('password_changed', False):
            return jsonify({'using_default': True})
    return jsonify({'using_default': False})

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # Admin dashboard cu statistici
    students = read_students()
    attendance = read_attendance()
    devices = read_devices()
    
    # Calculeaza statistici
    total_students = len(students)
    total_attendance = len(attendance)
    students_with_devices = len(devices)
    
    # Se iau ultimele 10 inregistrari de prezenta
    recent_attendance = []
    for record in reversed(attendance[-10:]):
        student = students.get(record['barcode_hash'], {})
        recent_attendance.append({
            'name': f"{student.get('surname', '')} {student.get('name', 'Unknown')}",
            'group': student.get('group', ''),
            'lesson_id': record['lesson_id'],
            'timestamp': record['timestamp']
        })
    
    stats = {
        'total_students': total_students,
        'total_attendance': total_attendance,
        'students_with_devices': students_with_devices,
        'recent_attendance': recent_attendance
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/generate-qr', methods=['GET', 'POST'])
@admin_required
def admin_generate_qr():
    # Genereaza cod QR pentru prezenta
    if request.method == 'POST':
        data = request.json
        lesson_id = data.get('lesson_id', '').strip()
        classroom = data.get('classroom', '').strip()
        session_id = data.get('session_id', '')  # Pentru rotirea QR-ului
        
        if not lesson_id or not classroom:
            return jsonify({'success': False, 'error': 'Trebuie sa completez id lectie si clasa'}), 400
        
        if classroom not in config.CLASSROOMS:
            return jsonify({'success': False, 'error': 'Clasa invalida, mai incearca'}), 400

        # Generare sau pastrare session_id
        if not session_id:
            session_id = secrets.token_urlsafe(16)
            session_start_time = time.time()
        else:
            # Pentru cererile de rotire, se foloseste aceeasi sesiune
            session_start_time = data.get('session_start_time', time.time())
        
        # Generare token QR si salvare in stocare persistenta
        qr_token = generate_qr_token()
        token_data = add_qr_token(qr_token, lesson_id, classroom)
        active_qr_tokens[qr_token] = token_data
        # Cod scurt de afisat (5 cifre random)
        import random
        display_code = str(random.randint(10000, 99999))
        
        # Se genereaza Codul QR cu URL-ul de verificare
        verify_url = url_for('verify_qr', token=qr_token, _external=True)
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(verify_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        img_base64 = base64.b64encode(img_io.getvalue()).decode()
        
        display_code_to_token[display_code] = qr_token  # Map the display code to the qr_token
        
        # Fix: fallback to database if not in memory
        if qr_token in active_qr_tokens:
            created_at = active_qr_tokens[qr_token]['created_at']
        else:
            # Fallback: get from database
            all_tokens = read_qr_tokens()
            created_at = all_tokens.get(qr_token, {}).get('created_at', time.time())

        return jsonify({
            'success': True,
            'qr_image': f'data:image/png;base64,{img_base64}',
            'qr_token': qr_token,
            'display_code': display_code,
            'expires_at': created_at + config.TOKEN_VALIDITY_SECONDS,
            'session_id': session_id,
            'session_start_time': session_start_time,
            'session_expires_at': session_start_time + config.SESSION_DURATION_SECONDS,
            'lesson_id': lesson_id,
            'classroom': classroom
        })
    
    classrooms = list(config.CLASSROOMS.keys())
    return render_template('admin/generate_qr.html', classrooms=classrooms)

@app.route('/admin/attendance')
@admin_required
def admin_attendance():
    # Se verifica prezentele cu filtre
    students = read_students()
    attendance = read_attendance()
    
    # Se parseaza filtrele din query string
    date_filter = request.args.get('date', '')
    lesson_filter = request.args.get('lesson', '')
    group_filter = request.args.get('group', '')
    
    # Se obtin valorile unice pentru filtre
    # Se sorteaza lectiile dupa data (timestamp-ul cel mai vechi pentru fiecare lectie)
    lesson_timestamps = {}
    for r in attendance:
        lesson_id = r['lesson_id']
        if lesson_id not in lesson_timestamps or r['timestamp'] < lesson_timestamps[lesson_id]:
            lesson_timestamps[lesson_id] = r['timestamp']
    lessons = sorted(lesson_timestamps.keys(), key=lambda x: lesson_timestamps.get(x, ''), reverse=True)
    groups = sorted(list(set(s['group'] for s in students.values() if s.get('group'))))
    
    # Construim lista de prezenta - afisam toti studentii din grupa selectata cu statusul de prezenta
    attendance_list = []
    
    if group_filter and lesson_filter:
        # Cand sunt selectate atat grupa cat si lectia, se afiseaza toti studentii din grupa respectiva
        # cu statusul lor de prezenta pentru lectia specifica, MULTUMIM BIANCAI si LUI DAVID, SUCA E CHIN
        for student_id, student in students.items():
            if student.get('group', '') != group_filter:
                continue
            
            # Verifica daca acest student este prezent pentru aceasta lectie
            is_present = False
            attendance_timestamp = ''
            for record in attendance:
                if record['barcode_hash'] == student_id and record['lesson_id'] == lesson_filter:
                    # Se referifica filtrul de data
                    if date_filter and not record['timestamp'].startswith(date_filter):
                        continue
                    is_present = True
                    attendance_timestamp = record['timestamp']
                    break
            
            attendance_list.append({
                'name': f"{student.get('surname', '')} {student.get('name', 'Unknown')}",
                'group': student.get('group', ''),
                'lesson_id': lesson_filter,
                'timestamp': attendance_timestamp if is_present else '-',
                'is_present': is_present,
                'student_id': student_id
            })
    else:
        # Daca nu se pune la legacy cum era, se afiseaza doar studentii care au prezenta inregistrata
        for record in attendance:
            student = students.get(record['barcode_hash'], {})
            
            # Filtrele se aplica
            if date_filter and not record['timestamp'].startswith(date_filter):
                continue
            if lesson_filter and record['lesson_id'] != lesson_filter:
                continue
            if group_filter and student.get('group', '') != group_filter:
                continue
            
            attendance_list.append({
                'name': f"{student.get('surname', '')} {student.get('name', 'Unknown')}",
                'group': student.get('group', ''),
                'lesson_id': record['lesson_id'],
                'timestamp': record['timestamp'],
                'is_present': True,
                'student_id': record['barcode_hash']
            })
    
    # Se sorteaza alfabetic dupa nume
    attendance_list.sort(key=lambda x: x['name'].lower())
    
    # Se calculeaza statistici cand se afiseaza grupa completa
    stats = None
    if group_filter and lesson_filter:
        total = len(attendance_list)
        present = sum(1 for s in attendance_list if s['is_present'])
        absent = total - present
        stats = {
            'total': total,
            'prezenti': present,
            'absenti': absent,
            'procentaj': round((present / total * 100) if total > 0 else 0, 1)
        }
    
    return render_template('admin/attendance.html', 
                         attendance=attendance_list,
                         lessons=lessons,
                         groups=groups,
                         stats=stats,
                         show_status=(group_filter and lesson_filter))

@app.route('/api/admin/toggle-attendance', methods=['POST'])
@admin_required
def toggle_attendance():
    # Toggle manual attendance pentru un student
    data = request.get_json()
    student_name = data.get('student_name')
    group = data.get('group')
    lesson_id = data.get('lesson_id')
    student_id = data.get('student_id')
    
    if not lesson_id:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    # Gaseste studentul: prefera ID-ul, altfel foloseste prenume+nume+grupa
    students = read_students()
    if not student_id:
        for sid, student in students.items():
            full_name = f"{student.get('surname', '')} {student.get('name', '')}"
            if full_name == (student_name or '') and student.get('group', '') == (group or ''):
                student_id = sid
                break
    
    if not student_id:
        return jsonify({'success': False, 'error': 'Student not found'}), 404
    
    # Verifica daca prezenta exista
    exists = db_check_attendance_exists(student_id, lesson_id)
    
    if exists:
        # Sterge prezenta (marca absent)
        success = db_delete_attendance(student_id, lesson_id)
        return jsonify({'success': success, 'is_present': False})
    else:
        # Adauga prezenta (marca prezent)
        success = db_write_attendance(student_id, lesson_id)
        return jsonify({'success': success, 'is_present': True})

@app.route('/admin/attendance/export/<format>')
@admin_required
def export_attendance(format):
    # Se exporta inregistrarile de prezenta Excel
    students = read_students()
    attendance = read_attendance()
    
    # Se iau filtrele din query string
    date_filter = request.args.get('date', '')
    lesson_filter = request.args.get('lesson', '')
    group_filter = request.args.get('group', '')
    
    # Construim lista de prezenta cu informatii despre studenti
    attendance_list = []
    for record in attendance:
        student = students.get(record['barcode_hash'], {})
        
        # Se aplica filtrele
        if date_filter and not record['timestamp'].startswith(date_filter):
            continue
        if lesson_filter and record['lesson_id'] != lesson_filter:
            continue
        if group_filter and student.get('group', '') != group_filter:
            continue
        
        attendance_list.append({
            'name': student.get('name', 'Unknown'),
            'surname': student.get('surname', ''),
            'group': student.get('group', ''),
            'lesson_id': record['lesson_id'],
            'timestamp': record['timestamp']
        })
    
    # Se pun alfabietic dupa prenume
    attendance_list.sort(key=lambda x: (x['surname'].lower(), x['name'].lower()))
    
    # Se genereaza numele fisierului
    filename_parts = ['Prezenta']
    if date_filter:
        filename_parts.append(date_filter)
    if lesson_filter:
        filename_parts.append(lesson_filter)
    if group_filter:
        filename_parts.append(group_filter)
    filename_base = '_'.join(filename_parts)
    
    if format == 'excel':
        # Se genereaza fisier Excel bine organizat, grupat pe grupe, Totul ca la carte!!
        output = io.StringIO()
        
        # PE GRUPE
        grouped_attendance = {}
        for record in attendance_list:
            group = record['group'] or 'Idee n-am'
            if group not in grouped_attendance:
                grouped_attendance[group] = []
            grouped_attendance[group].append(record)
        
        # Se sorteaza grupele alfabetic
        sorted_groups = sorted(grouped_attendance.keys())
        
        # Functie ajutatoare pentru a completa coloanele cu spatii, sa arate bine
        def pad(text, width):
            return str(text).ljust(width)
        
        # Latimi coloane
        col_num = 5
        col_name = 20
        col_surname = 20
        col_lesson = 20
        col_timestamp = 22
        
        # Scriem titlul si informatiile de filtru
        output.write('Raport cu prezentele:)\n')
        output.write(f'Generat la :      {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        if date_filter:
            output.write(f'Data:    {date_filter}\n')
        if lesson_filter:
            output.write(f'Lectia:  {lesson_filter}\n')
        if group_filter:
            output.write(f'Grupa:   {group_filter}\n')
        output.write('\n')
        
        # Scriem rezumat
        output.write('Rezumat\n')
        output.write(f'Toate inregistrarile:  {len(attendance_list)}\n')
        output.write(f'Total Grupi:   {len(sorted_groups)}\n')
        output.write('\n')
        output.write('=' * 90 + '\n')
        output.write('\n')
        
        # Scriem datele organizate pe grupe
        for group in sorted_groups:
            group_records = grouped_attendance[group]
            
            # Se sorteaza inregistrarile din grupa dupa prenume si nume
            group_records.sort(key=lambda x: (x['surname'].lower(), x['name'].lower()))
            
            # Antet grupa
            output.write(f'GRUPA: {group}    (Studenti: {len(group_records)})\n')
            output.write('-' * 90 + '\n')
            
            # Antet coloane
            output.write(f'{pad("#", col_num)}{pad("Prenume", col_surname)}{pad("Nume", col_name)}{pad("Lectia", col_lesson)}{pad("Timestamp", col_timestamp)}\n')
            output.write('-' * 90 + '\n')
            
            # Date grupa
            for i, record in enumerate(group_records, 1):
                output.write(f'{pad(i, col_num)}{pad(record["surname"], col_surname)}{pad(record["name"], col_name)}{pad(record["lesson_id"], col_lesson)}{pad(record["timestamp"], col_timestamp)}\n')
            
            output.write('\n')
        
        output.seek(0)
        
        # Se adauga BOM pentru UTF-8 la Excel
        response = make_response('\ufeff' + output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.ms-excel; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename={filename_base}.xls'
        return response
    
    return jsonify({'success': False, 'error': 'Format invalid, ceva nu e in regula'}), 400

@app.route('/admin/students', methods=['GET', 'POST'])
@admin_required
def admin_students():
    # Genstionare a studentilor
    if request.method == 'POST':
        action = request.json.get('action')
        
        if action == 'add':
            name = request.json.get('name', '').strip()
            surname = request.json.get('surname', '').strip()
            group = request.json.get('group', '').strip()
            barcode = request.json.get('barcode', '').strip()  # Optional
            
            if not all([name, surname, group]):
                return jsonify({'success': False, 'error': 'Numele, prenumele si grupa trebuie completate'}), 400

            # Validate no pipe characters (used as delimiter in storage)
            if any('|' in field for field in [name, surname, group]):
                return jsonify({'success': False, 'error': 'Name, surname, and group nu pot contine |'}), 400
            
            # Validate barcode only if provided
            if barcode and (len(barcode) != 8 or not barcode.isdigit()):
                return jsonify({'success': False, 'error': 'Barcode trebuie sa aiba 8 cifre'}), 400
            
            students = read_students()
            student_id = generate_student_id(name, surname, group)
            if student_id in students:
                return jsonify({'success': False, 'error': 'Studentul exista deja'}), 400
            
            # Barcodule este Hashuit intern
            add_student(name, surname, group, barcode)
            return jsonify({'success': True, 'message': 'Student adaugat cu succes:)'})
        
        elif action == 'delete':
            student_id = request.json.get('student_id', '').strip()
            students = read_students()
            
            if student_id not in students:
                return jsonify({'success': False, 'error': 'Studentul nu a fost gasit:('}), 400

            # Se sterge studentul din baza de date
            db_delete_student(student_id)

            return jsonify({'success': True, 'message': 'Student sters cu succes'})

        elif action == 'reset_device':
            student_id = request.json.get('student_id', '').strip()
            
            # Se sterge device-ul direct din baza de date
            db_delete_device(student_id)
            
            return jsonify({'success': True, 'message': 'Sa resetat tokenul de device cu succes'})
    
    # Se arata lista de studenti
    students = read_students()
    devices = read_devices()
    
    students_list = []
    for barcode_hash, student in students.items():
        device_info = devices.get(barcode_hash, {})
        students_list.append({
            'id': barcode_hash,
            'name': student['name'],
            'surname': student['surname'],
            'group': student['group'],
            'has_device': barcode_hash in devices,
            'device_type': device_info.get('device_type', 'unknown') if barcode_hash in devices else None,
            'registered_at': student.get('timestamp', '')
        })
    
    # Se sorteaza alfabetic dupa prenume
    students_list.sort(key=lambda x: (x['surname'].lower(), x['name'].lower()))
    
    return render_template('admin/students.html', students=students_list)

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    # System settings
    if request.method == 'POST':
        action = request.json.get('action')
        
        if action == 'update_ips':
    
            return jsonify({'success': True, 'message': 'Setarile IP au fost actualizate'})
        
        elif action == 'update_classroom':
            
            return jsonify({'success': True, 'message': 'Clasa a fost actualizata cu succes'})
        
        elif action == 'change_password':
            current_password = request.json.get('current_password', '').strip()
            new_password = request.json.get('new_password', '').strip()
            confirm_password = request.json.get('confirm_password', '').strip()
            
            if not current_password or not new_password or not confirm_password:
                return jsonify({'success': False, 'error': 'Tot trebuis sa fie completat'}), 400
            
            if new_password != confirm_password:
                return jsonify({'success': False, 'error': 'Noile parole nu se potrivesc'}), 400

            if len(new_password) < 6:
                return jsonify({'success': False, 'error': 'Parola trebuie sa aiba cel putin 6 caractere'}), 400

            # Se verifica parola curenta
            username = session.get('username')
            teachers = read_teachers()
            if username not in teachers or hash_password(current_password) != teachers[username]['password_hash']:
                return jsonify({'success': False, 'error': 'Parola nu este corecta'}), 401
            
            # Se actualizeaza parola
            if update_teacher_password(username, new_password):
                session['password_changed'] = True
                return jsonify({'success': True, 'message': 'Parola a fost schimbata cu succes'})
            else:
                return jsonify({'success': False, 'error': 'Nu sa schimbat parola'}), 500
    
    return render_template('admin/settings.html', 
                         allowed_ips=config.ALLOWED_PUBLIC_IPS,
                         classrooms=config.CLASSROOMS,
                         username=session.get('username', ''),
                         password_changed=session.get('password_changed', False))

@app.route('/admin/scanner')
@admin_required
def admin_scanner():
    # Barcode scanner cu webcam
    return render_template('admin/scanner.html')

#Registarere cu QRCODE

@app.route('/admin/registration-qr')
@admin_required
def admin_registration_qr():
        # Genereaza un cod QR care directioneaza studentii catre pagina de inregistrare
        # Se construieste URL-ul absolut pentru inregistrare
        proto = request.headers.get('X-Forwarded-Proto', request.scheme)
        host = request.headers.get('Host', request.host)
        registration_url = f"{proto}://{host}/register"

        # Se genereaza imaginea QR
        qr_img = qrcode.make(registration_url)
        img_bytes = io.BytesIO()
        qr_img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        qr_base64 = base64.b64encode(img_bytes.read()).decode('utf-8')

        return render_template('admin/generate_registration_qr.html',
                                                     registration_url=registration_url,
                                                     qr_base64=qr_base64)

## Api pentru scannerul de coduri de bare

@app.route('/api/scanner/check/<barcode>')
@admin_required
def scanner_check_student(barcode):
    # Verifica daca studentul exista si returneaza informatiile sale (doar admin)
    students = read_students()
    barcode_hash = hash_barcode(barcode)
    
    # Se cauta studentul dupa hash-ul codului de bare stocat
    found_student = None
    found_student_id = None
    for student_id, student in students.items():
        if student.get('barcode') == barcode_hash:
            found_student = student
            found_student_id = student_id
            break
    
    if not found_student:
        return jsonify({'success': False, 'error': 'Studentul nu a fost gasit:('}), 404
    
    return jsonify({
        'success': True,
        'student': {
            'name': found_student['name'],
            'surname': found_student['surname'],
            'group': found_student['group']
        }
    })

@app.route('/api/scanner/mark', methods=['POST'])
def scanner_mark_attendance():
    # Marcheaza prezenta pentru un student folosind codul de bare (doar admin)
    # Se verifica daca adminul este logat
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Neautorizat'}), 401
    
    data = request.json
    barcode = data.get('barcode', '').strip()
    lesson_id = data.get('lesson_id', '').strip()
    
    # Se valideaza inputurile
    if not barcode or not lesson_id:
        return jsonify({'success': False, 'error': 'Trebui sa completezi tot'}), 400
    
    # Se verifica daca studentul exista cautand hash-ul codului de bare, pentru temosi
    students = read_students()
    barcode_hash = hash_barcode(barcode)
    
    found_student = None
    found_student_id = None
    for student_id, student in students.items():
        if student.get('barcode') == barcode_hash:
            found_student = student
            found_student_id = student_id
            break
    
    if not found_student:
        return jsonify({'success': False, 'error': 'Studentul nu a fost gasit in sistem:('}), 404
    
    student = found_student
    
    # Se verifica daca prezenta a fost deja marcata
    attendance = read_attendance()
    for record in attendance:
        if record['barcode_hash'] == found_student_id and record['lesson_id'] == lesson_id:
            return jsonify({'success': False, 'error': 'Deja sa facut prezenta la tine'}), 400
    
    # Se marcheaza prezenta folosind student_id pentru consistenta
    write_attendance_by_student_id(found_student_id, lesson_id)
    
    return jsonify({
        'success': True,
        'message': f'Prezenta sa facut cu succes pentru {student["name"]} {student["surname"]}, super:)',
        'student': {
            'name': student['name'],
            'surname': student['surname'],
            'group': student['group']
        }
    })

# Curatare in general a programei

def cleanup_expired_tokens():
    # Se curata tokenurile QR expirate periodic
    # Se curata tokenurile QR, sa nu creasca la infinit
    db_cleanup_qr_tokens(config.TOKEN_VALIDITY_SECONDS + 10)
    
    # Se curata cooldown-urile dispozitivelor, sa nu creasca la infinit
    db_cleanup_device_cooldowns(config.DEVICE_REREGISTER_COOLDOWN_SECONDS)
    
    # Se actualizeaza in-memory 
    active_qr_tokens.clear()
    active_qr_tokens.update(read_qr_tokens())

@app.before_request
def before_request():
    # Se ruleaza inainte de fiecare cerere
    # Se incaraca tokenurile QR active in memorie daca nu sunt deja incarcate
    if not active_qr_tokens:
        active_qr_tokens.update(read_qr_tokens())
    cleanup_expired_tokens()

@app.route('/debug-test') #Pentru testare erori in debug, HIHIC
def debug_test():
    x = 1 / 0
    return "test"
# AICI SE TERMINA TOTUL, SI SE PORNESTE SERVERUL

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=config.DEBUG)
