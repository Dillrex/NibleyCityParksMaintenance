from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__)
app.secret_key = 'NibleyCityParks9325743'
DB_PATH = 'database.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, is_admin INTEGER DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY, name TEXT, type TEXT, status TEXT, oil_interval INTEGER, next_oil_change DATE)""")
        c.execute("""CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY, equipment_id INTEGER, content TEXT, timestamp TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY, equipment_id INTEGER, equipment_name TEXT, issue TEXT,
            submitted_at TEXT, completed INTEGER DEFAULT 0)""")
        c.execute("INSERT OR IGNORE INTO users (username, password, is_admin) VALUES (?, ?, ?)", ('Rod', 'Rod', 1))
        conn.commit()

init_db()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT id, is_admin FROM users WHERE username = ? AND password = ?", (username, password))
            user = c.fetchone()
            if user:
                session['user'] = username
                session['user_id'] = user[0]
                session['admin'] = bool(user[1])
                return redirect(url_for('dashboard'))
            error = 'Invalid credentials'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=session['user'], is_admin=session.get('admin', False))

@app.route('/equipment', methods=['GET', 'POST'])
def equipment():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        type_ = request.form['type']
        status = request.form['status']
        oil_interval = int(request.form['oil_interval'])
        next_due = (datetime.now() + timedelta(days=oil_interval)).date()
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO equipment (name, type, status, oil_interval, next_oil_change) VALUES (?, ?, ?, ?, ?)",
                      (name, type_, status, oil_interval, next_due))
        return redirect(url_for('dashboard'))
    return render_template('equipment_form.html')

@app.route('/equipment/<int:equipment_id>/note', methods=['POST'])
def add_note(equipment_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    note = request.form['note']
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO notes (equipment_id, content, timestamp) VALUES (?, ?, ?)", (equipment_id, note, timestamp))
    return redirect(url_for('dashboard'))

@app.route('/api/equipment')
def api_equipment():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, type, status, oil_interval, next_oil_change FROM equipment")
        rows = c.fetchall()
        equipment = []
        for row in rows:
            days = (datetime.strptime(row[5], "%Y-%m-%d") - datetime.now()).days
            equipment.append({
                "id": row[0], "name": row[1], "type": row[2],
                "status": row[3], "oil_interval": row[4],
                "next_oil_change": row[5], "days_remaining": days
            })
        return jsonify(equipment)

@app.route('/submit_ticket', methods=['GET', 'POST'])
def submit_ticket():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, name FROM equipment")
        equipment_list = c.fetchall()

    if request.method == 'POST':
        eq_id = request.form.get('equipment_id')
        eq_name = request.form.get('custom_name')
        issue = request.form['issue']
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            if eq_id:
                c.execute("INSERT INTO tickets (equipment_id, equipment_name, issue, submitted_at) VALUES (?, ?, ?, ?)",
                          (eq_id, '', issue, timestamp))
                c.execute("UPDATE equipment SET status = ? WHERE id = ?", ('Broken', eq_id))
            else:
                c.execute("INSERT INTO equipment (name, type, status, oil_interval, next_oil_change) VALUES (?, ?, ?, ?, ?)",
                          (eq_name, 'Unknown', 'Broken', 30, (datetime.now() + timedelta(days=30)).date()))
                new_id = c.lastrowid
                c.execute("INSERT INTO tickets (equipment_id, equipment_name, issue, submitted_at) VALUES (?, ?, ?, ?)",
                          (new_id, '', issue, timestamp))
        return redirect(url_for('submit_ticket'))

    return render_template('submit_ticket.html', equipment=equipment_list)

@app.route('/tickets')
def view_tickets():
    if 'user' not in session:
        return redirect(url_for('login'))
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, equipment_id, issue, submitted_at, completed FROM tickets WHERE completed = 0")
        tickets = c.fetchall()
    return render_template('tickets.html', tickets=tickets)

@app.route('/tickets/<int:ticket_id>/complete', methods=['POST'])
def complete_ticket(ticket_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT equipment_id, issue FROM tickets WHERE id = ?", (ticket_id,))
        ticket = c.fetchone()
        if ticket:
            eq_id, issue = ticket
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute("UPDATE equipment SET status = ? WHERE id = ?", ("Working", eq_id))
            c.execute("INSERT INTO notes (equipment_id, content, timestamp) VALUES (?, ?, ?)",
                      (eq_id, f"Ticket resolved: {issue}", timestamp))
            c.execute("UPDATE tickets SET completed = 1 WHERE id = ?", (ticket_id,))
    return redirect(url_for('view_tickets'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'user' not in session or not session.get('admin'):
        return redirect(url_for('login'))
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        if request.method == 'POST':
            if 'add_user' in request.form:
                new_user = request.form['new_username']
                new_pass = request.form['new_password']
                is_admin = 1 if 'is_admin' in request.form else 0
                c.execute("INSERT OR IGNORE INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                          (new_user, new_pass, is_admin))
            elif 'remove_user' in request.form:
                user_id = request.form['user_id']
                c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        c.execute("SELECT id, username, is_admin FROM users")
        users = c.fetchall()
    return render_template('admin_panel.html', users=users)


@app.route('/equipment/<int:equipment_id>/update', methods=['POST'])
def update_equipment(equipment_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    status = request.form['status']
    oil_interval = int(request.form['oil_interval'])
    next_due = (datetime.now() + timedelta(days=oil_interval)).date()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE equipment SET status = ?, oil_interval = ?, next_oil_change = ? WHERE id = ?",
                  (status, oil_interval, next_due, equipment_id))
        c.execute("INSERT INTO notes (equipment_id, content, timestamp) VALUES (?, ?, ?)",
                  (equipment_id, f"Updated status to '{status}' and interval to {oil_interval} days", timestamp))
    return redirect(url_for('dashboard'))



@app.route('/tickets/unread')
def unread_tickets():
    if 'user' not in session:
        return jsonify({"new_tickets": False})
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM tickets WHERE completed = 0")
        count = c.fetchone()[0]
    return jsonify({"new_tickets": count > 0})
