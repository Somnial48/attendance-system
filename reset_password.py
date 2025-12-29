#!/usr/bin/env python3
"""
Resetarea parole
Utilizare: python3 reset_password.py [username] [new_password]
Daca nu pui nimic , resets 'admin' to 'admin123'
"""

import hashlib
import sys
import os

# Se adauga calea curenta pentru a importa modulul database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db_read_teachers, db_write_teacher

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def reset_password(username='admin', new_password='admin123'):
    teachers = db_read_teachers()
    
    if username not in teachers:
        print(f"Eroare: Utilizatorul '{username}' nu a fost gasit in baza de date")
        return False
    
    teacher = teachers[username]
    password_changed = new_password != 'admin123'
    
    db_write_teacher(
        username,
        hash_password(new_password),
        teacher['display_name'],
        teacher.get('role', 'teacher'),
        password_changed
    )
    
    print(f"Parola pentru '{username}' a fost schimbata in: {new_password}")
    return True

if __name__ == '__main__':
    if len(sys.argv) == 3:
        # python3 reset_password.py username parola
        reset_password(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        # python3 reset_password.py username (reset to admin123)
        reset_password(sys.argv[1], 'admin123')
    else:
        # Nici un argument - reseteaza admin la admin123
        print("Nici un argument, resetand 'admin' la parola default 'admin123'")
        reset_password('admin', 'admin123')
