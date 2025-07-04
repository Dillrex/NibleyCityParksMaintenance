from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    db = get_db()
    db.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        is_admin INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        status TEXT,
        oil_interval INTEGER,
        last_oil_change TEXT
    );
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id INTEGER,
        content TEXT,
        timestamp TEXT
    );
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id INTEGER,
        equipment_name TEXT,
        issue TEXT,
        complete INTEGER DEFAULT 0,
        unread INTEGER DEFAULT 1
    );
    ''')
    try:
        db.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)", ('Rod', 'admin', 1))
    except sqlite3.IntegrityError:
        pass
    db.commit()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()
        if user:
            session['user'] = user['username']
            session['is_admin'] = bool(user['is_admin'])
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    db = get_db()
    equipment_raw = db.execute("SELECT * FROM equipment").fetchall()
    equipment = []
    for e in equipment_raw:
        last_oil = datetime.strptime(e['last_oil_change'], "%Y-%m-%d").date()
        days_left = e['oil_interval'] - (datetime.today().date() - last_oil).days
        e = dict(e)
        e['days_left'] = max(days_left, 0)
        equipment.append(e)

    unread = db.execute("SELECT COUNT(*) FROM tickets WHERE unread=1").fetchone()[0]
    return render_template('dashboard.html', user=session['user'], is_admin=session.get('is_admin', False), equipment=equipment, unread=unread)

@app.route('/add_equipment', methods=['GET', 'POST'])
def add_equipment():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        status = request.form['status']
        if status == '__custom__':
            status = request.form.get('custom_status', status)
        interval = int(request.form['interval'])
        db = get_db()
        db.execute("INSERT INTO equipment (name, status, oil_interval, last_oil_change) VALUES (?, ?, ?, ?)",
                   (name, status, interval, datetime.today().strftime('%Y-%m-%d')))
        db.commit()
        return redirect(url_for('dashboard'))
    return render_template('equipment.html')

@app.route('/update_equipment/<int:equipment_id>', methods=['POST'])
def update_equipment(equipment_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    status = request.form['status']
    if status == '__custom__':
        status = request.form.get('custom_status', status)
    interval = request.form['interval']
    db = get_db()
    db.execute("UPDATE equipment SET status=?, oil_interval=? WHERE id=?", (status, interval, equipment_id))
    db.execute("INSERT INTO notes (equipment_id, content, timestamp) VALUES (?, ?, ?)",
               (equipment_id, f"Updated status to {status} and oil interval to {interval} days", datetime.now().isoformat()))
    db.commit()
    return redirect(url_for('dashboard'))

@app.route('/tickets')
def view_tickets():
    if 'user' not in session:
        return redirect(url_for('login'))

    db = get_db()
    tickets = db.execute("SELECT * FROM tickets WHERE complete=0").fetchall()
    return render_template('tickets.html', tickets=tickets)

@app.route('/admin')
def admin_panel():
    if not session.get('is_admin'):
        return redirect(url_for('dashboard'))

    db = get_db()
    users = db.execute("SELECT * FROM users").fetchall()
    return render_template('admin.html', users=users)

@app.route('/notes/<int:equipment_id>')
def view_notes(equipment_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    db = get_db()
    equipment = db.execute("SELECT * FROM equipment WHERE id = ?", (equipment_id,)).fetchone()
    notes = db.execute("SELECT * FROM notes WHERE equipment_id = ? ORDER BY timestamp DESC", (equipment_id,)).fetchall()
    return render_template('notes.html', equipment=equipment, notes=notes)

@app.route('/add_note/<int:equipment_id>', methods=['POST'])
def add_note(equipment_id):
    content = request.form.get('note')
    if not content:
        return "Note content cannot be empty", 400

    db = get_db()
    db.execute("INSERT INTO notes (equipment_id, content, timestamp) VALUES (?, ?, ?)",
               (equipment_id, content, datetime.now().isoformat()))
    db.commit()
    return redirect(url_for('view_notes', equipment_id=equipment_id))

@app.route('/edit_note/<int:note_id>', methods=['POST'])
def edit_note(note_id):
    new_content = request.form.get('note')
    if not new_content:
        return "Note content is required", 400

    db = get_db()
    db.execute("UPDATE notes SET content = ?, timestamp = ? WHERE id = ?", 
               (new_content, datetime.now().isoformat(), note_id))
    db.commit()
    equipment_id = db.execute("SELECT equipment_id FROM notes WHERE id = ?", (note_id,)).fetchone()['equipment_id']
    return redirect(url_for('view_notes', equipment_id=equipment_id))

@app.route('/delete_note/<int:note_id>')
def delete_note(note_id):
    db = get_db()
    equipment_id = db.execute("SELECT equipment_id FROM notes WHERE id = ?", (note_id,)).fetchone()['equipment_id']
    db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    db.commit()
    return redirect(url_for('view_notes', equipment_id=equipment_id))

@app.route('/add_user', methods=['POST'])
def add_user():
    username = request.form['username']
    password = request.form['password']
    is_admin = 1 if 'is_admin' in request.form else 0
    db = get_db()
    try:
        db.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)", (username, password, is_admin))
        db.commit()
    except sqlite3.IntegrityError:
        pass
    return redirect(url_for('admin_panel'))

@app.route('/change_password', methods=['POST'])
def change_password():
    username = request.form.get('username')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')

    if not username or not current_password or not new_password:
        return "Missing required fields", 400

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if user is None or user['password'] != current_password:
        return "Invalid current password", 403

    db.execute("UPDATE users SET password = ? WHERE username = ?", (new_password, username))
    db.commit()

    return redirect(url_for('admin_panel'))

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return redirect(url_for('admin_panel'))

@app.route('/delete_equipment/<int:equipment_id>')
def delete_equipment(equipment_id):
    db = get_db()
    db.execute("DELETE FROM equipment WHERE id = ?", (equipment_id,))
    db.execute("DELETE FROM notes WHERE equipment_id = ?", (equipment_id,))
    db.execute("DELETE FROM tickets WHERE equipment_id = ?", (equipment_id,))
    db.commit()
    return redirect(url_for('dashboard'))

@app.route('/submit_ticket', methods=['GET', 'POST'])
def submit_ticket():
    db = get_db()
    if request.method == 'POST':
        equipment_id = request.form.get('equipment_id')
        equipment_name = request.form.get('equipment_name')
        issue = request.form.get('issue')

        if equipment_id:
            equipment_id = int(equipment_id)
            equipment = db.execute("SELECT name FROM equipment WHERE id = ?", (equipment_id,)).fetchone()
            equipment_name = equipment['name'] if equipment else equipment_name
        else:
            db.execute("INSERT INTO equipment (name, status, oil_interval, last_oil_change) VALUES (?, ?, ?, ?)",
                       (equipment_name, 'Reported Issue', 30, datetime.today().strftime('%Y-%m-%d')))
            equipment_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        db.execute("INSERT INTO tickets (equipment_id, equipment_name, issue, unread) VALUES (?, ?, ?, 1)",
                   (equipment_id, equipment_name, issue))
        db.execute("UPDATE equipment SET status = ? WHERE id = ?", ('Reported Issue', equipment_id))
        db.commit()
        return redirect(url_for('login'))

    equipment = db.execute("SELECT * FROM equipment").fetchall()
    return render_template('submit_ticket.html', equipment=equipment)

@app.route('/mark_ticket_read/<int:ticket_id>')
def mark_ticket_read(ticket_id):
    db = get_db()
    db.execute("UPDATE tickets SET unread = 0 WHERE id = ?", (ticket_id,))
    db.commit()
    return redirect(url_for('view_tickets'))

@app.route('/complete_ticket/<int:ticket_id>')
def complete_ticket(ticket_id):
    db = get_db()
    db.execute("UPDATE tickets SET complete = 1, unread = 0 WHERE id = ?", (ticket_id,))
    db.commit()
    return redirect(url_for('view_tickets'))

@app.route('/mark_all_read')
def mark_all_read():
    db = get_db()
    db.execute("UPDATE tickets SET unread = 0 WHERE unread = 1")
    db.commit()
    return redirect(url_for('view_tickets'))

if __name__ == '__main__':
    create_tables()
    app.run(debug=True)
