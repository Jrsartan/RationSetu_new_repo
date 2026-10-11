from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import hashlib
import threading
import time
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'rationSetu2024SecretKey')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'ration_setu.db')

# ─────────────────────────────────────────────
# Try to import serial (optional)
# ─────────────────────────────────────────────
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("⚠️  pyserial not installed - Running in Demo Mode")

# ─────────────────────────────────────────────
# DATABASE HELPER
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ─────────────────────────────────────────────
# ESP32 SERIAL CONNECTION
# ─────────────────────────────────────────────
esp32_port = None
fingerprint_status = {"verified": False, "id": None}

def connect_esp32():
    global esp32_port
    if not SERIAL_AVAILABLE:
        print("⚠️  Running without ESP32 - Demo Mode Active")
        return
    try:
        esp32_port = serial.Serial(os.environ.get('ESP32_PORT', 'COM3'), 115200, timeout=1)
        print("✅ ESP32 Connected!")
    except Exception as e:
        print(f"⚠️  ESP32 not connected: {e}")
        print("⚠️  Running in Demo Mode")
        esp32_port = None

def read_esp32():
    global fingerprint_status
    while True:
        if esp32_port and esp32_port.is_open:
            try:
                line = esp32_port.readline().decode('utf-8').strip()
                if line.startswith("FINGER_OK:"):
                    fid = line.split(":")[1]
                    fingerprint_status["verified"] = True
                    fingerprint_status["id"] = fid
                elif line == "FINGER_FAIL":
                    fingerprint_status["verified"] = False
                    fingerprint_status["id"] = None
            except Exception:
                pass
        time.sleep(0.1)

# Start ESP32
connect_esp32()
esp32_thread = threading.Thread(target=read_esp32, daemon=True)
esp32_thread.start()

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

# Landing Page
@app.route('/')
def index():
    return render_template('index.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user_id  = request.form['user_id']
        password = request.form['password']
        hashed   = hash_password(password)

        db   = get_db()
        user = db.execute(
            'SELECT * FROM admins WHERE user_id=? AND password=?',
            (user_id, hashed)
        ).fetchone()
        db.close()

        if user:
            session['logged_in'] = True
            session['user_id']   = user_id
            session['username']  = user['username']
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid User ID or Password!'

    return render_template('login.html', error=error)

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Dashboard
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    db    = get_db()
    users = db.execute('SELECT * FROM users WHERE is_active=1 ORDER BY id').fetchall()
    db.close()
    return render_template('all_users.html', users=users)

# Manage Users
@app.route('/manage_users')
def manage_users():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('manage_users.html')

# API: Fingerprint Status
@app.route('/api/fingerprint_status')
def api_fingerprint_status():
    return jsonify(fingerprint_status)

# API: Scan Fingerprint
@app.route('/api/scan_fingerprint', methods=['POST'])
def scan_fingerprint():
    global fingerprint_status
    fingerprint_status = {"verified": False, "id": None}

    if esp32_port and esp32_port.is_open:
        esp32_port.write(b'SCAN\n')
        return jsonify({"status": "scanning"})
    else:
        # DEMO MODE
        def demo_verify():
            global fingerprint_status
            time.sleep(3)
            fingerprint_status["verified"] = True
            fingerprint_status["id"] = "1"

        demo_thread = threading.Thread(target=demo_verify, daemon=True)
        demo_thread.start()
        return jsonify({"status": "demo_mode"})

# API: Enroll Fingerprint
@app.route('/api/enroll_fingerprint', methods=['POST'])
def enroll_fingerprint():
    data      = request.json
    finger_id = data.get('finger_id', 1)
    if esp32_port and esp32_port.is_open:
        cmd = f'ENROLL:{finger_id}\n'
        esp32_port.write(cmd.encode())
        return jsonify({"status": "enrolling", "id": finger_id})
    return jsonify({"status": "demo_enrolled", "id": finger_id})

# Add User
@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        aadhar   = request.form['aadhar']
        family_m = request.form['family_members']
        head     = request.form['head_of_family']
        member2  = request.form['member2']
        member3  = request.form['member3']
        bank_ac  = request.form['bank_ac']
        mobile   = request.form['mobile']
        address  = request.form['address']
        district = request.form['district']
        state    = request.form['state']
        finger_id = request.form.get('finger_id', '0')

        db = get_db()
        try:
            db.execute('''
                INSERT INTO users
                (aadhar_no, family_members, head_of_family,
                 member2, member3, bank_ac, mobile,
                 address, district, state, finger_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ''', (aadhar, family_m, head, member2,
                  member3, bank_ac, mobile, address,
                  district, state, finger_id))
            db.commit()
            db.close()
            return redirect(url_for('dashboard'))
        except sqlite3.IntegrityError:
            db.close()
            return render_template('add_user.html',
                                   error='Aadhar number already exists!')

    finger_id = request.args.get('finger_id', '0')
    return render_template('add_user.html', finger_id=finger_id)

# Ration Distribution
@app.route('/ration_distribution')
def ration_distribution():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    db          = get_db()
    commodities = db.execute('SELECT * FROM commodities').fetchall()
    db.close()
    return render_template('ration_distribution.html',
                           commodities=commodities)

# Process Ration
@app.route('/process_ration', methods=['POST'])
def process_ration():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        commodity_name = request.form['commodity_name']
        qty = float(request.form['qty'])
    except (KeyError, ValueError):
        return "Invalid quantity.", 400

    if qty <= 0:
        return "Quantity must be greater than zero.", 400

    db = get_db()
    commodity = db.execute(
        "SELECT * FROM commodities WHERE name=? AND is_active=1",
        (commodity_name,)
    ).fetchone()

    if not commodity:
        db.close()
        return "Invalid Commodity!", 400

    if qty > commodity['eligibility_qty']:
        db.close()
        return f"Maximum eligible quantity is {commodity['eligibility_qty']} {commodity['unit']}.", 400

    if qty > commodity['remaining_qty']:
        db.close()
        return "Insufficient stock available.", 400

    total_amount = qty * commodity['rate']
    remaining = commodity['remaining_qty'] - qty

    db.execute(
        "UPDATE commodities SET remaining_qty=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (remaining, commodity['id'])
    )
    db.execute("""
        INSERT INTO distribution_log
        (commodity_id, commodity_name, qty_distributed, rate, total_amount)
        VALUES (?, ?, ?, ?, ?)
    """, (commodity['id'], commodity['name'], qty, commodity['rate'], total_amount))
    db.commit()
    db.close()

    if esp32_port and esp32_port.is_open:
        esp32_port.write(f'DISPENSE:{qty}\n'.encode())

    return render_template(
        'payment.html',
        commodity={
            "name": commodity['name'],
            "eligibility_qty": commodity['eligibility_qty'],
            "rate": commodity['rate'],
            "unit": commodity['unit']
        },
        qty=qty,
        total_amount=total_amount,
        remaining=remaining
    )

# Change Password
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    message = None
    if request.method == 'POST':
        old_pass = hash_password(request.form['old_password'])
        new_pass = hash_password(request.form['new_password'])

        db   = get_db()
        user = db.execute(
            'SELECT * FROM admins WHERE user_id=? AND password=?',
            (session['user_id'], old_pass)
        ).fetchone()

        if user:
            db.execute(
                'UPDATE admins SET password=? WHERE user_id=?',
                (new_pass, session['user_id'])
            )
            db.commit()
            message = "Password changed successfully!"
        else:
            message = "Old password incorrect!"
        db.close()

    return render_template('change_password.html', message=message)

# API: Get Weight
@app.route('/api/get_weight')
def get_weight():
    if esp32_port and esp32_port.is_open:
        esp32_port.write(b'WEIGHT\n')
        time.sleep(0.5)
        weight = esp32_port.readline().decode().strip()
        return jsonify({"weight": weight})
    return jsonify({"weight": "0.00"})

# API: Tare Scale
@app.route('/api/tare_scale', methods=['POST'])
def tare_scale():
    if esp32_port and esp32_port.is_open:
        esp32_port.write(b'TARE\n')
        return jsonify({"status": "tared"})
    return jsonify({"status": "demo_tared"})

# API: Delete User
@app.route('/api/delete_user/<int:user_id>', methods=['DELETE'])
def api_delete_user(user_id):
    if not session.get('logged_in'):
        return jsonify({"success": False}), 401
    db = get_db()
    db.execute('UPDATE users SET is_active=0 WHERE id=?', (user_id,))
    db.commit()
    db.close()
    return jsonify({"success": True})

# API: Stats
@app.route('/api/stats')
def api_stats():
    if not session.get('logged_in'):
        return jsonify({}), 401
    db = get_db()
    total_users = db.execute(
        'SELECT COUNT(*) as count FROM users'
    ).fetchone()['count']
    db.close()
    return jsonify({'total_users': total_users})

if __name__ == '__main__':
    from database import init_db
    init_db()
    print("\n🌐 Starting Flask Server...")
    print("📌 Open browser and go to: http://127.0.0.1:5000")
    print("📌 Press Ctrl+C to stop server\n")
    app.run(debug=True, host='0.0.0.0', port=5000)