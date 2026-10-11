import sqlite3
import hashlib
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "ration_setu.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aadhar_no TEXT UNIQUE NOT NULL,
            family_members INTEGER DEFAULT 1,
            head_of_family TEXT,
            member2 TEXT DEFAULT '',
            member3 TEXT DEFAULT '',
            bank_ac TEXT DEFAULT '',
            mobile TEXT,
            address TEXT,
            district TEXT,
            state TEXT,
            finger_id TEXT DEFAULT '0',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commodities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            eligibility_qty REAL DEFAULT 0,
            rate REAL DEFAULT 0,
            remaining_qty REAL DEFAULT 0,
            unit TEXT DEFAULT 'kg',
            is_active INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS distribution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            aadhar_no TEXT,
            commodity_id INTEGER,
            commodity_name TEXT,
            qty_distributed REAL,
            rate REAL,
            total_amount REAL,
            distributed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (commodity_id) REFERENCES commodities(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fingerprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finger_id TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            aadhar_no TEXT,
            enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)


def insert_default_data(cursor):
    cursor.execute(
        "INSERT OR IGNORE INTO admins (user_id, username, password) VALUES (?, ?, ?)",
        ("admin", "Admin", hash_password("admin123"))
    )

    commodities = [
        ("Wheat", 5, 2, 500, "kg"),
        ("Rice", 5, 3, 400, "kg"),
        ("Sugar", 2, 20, 200, "kg"),
        ("Dal", 3, 40, 300, "kg"),
    ]
    for item in commodities:
        cursor.execute("""
            INSERT OR IGNORE INTO commodities
            (name, eligibility_qty, rate, remaining_qty, unit)
            VALUES (?, ?, ?, ?, ?)
        """, item)

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO users
            (aadhar_no, family_members, head_of_family, member2, member3,
             bank_ac, mobile, address, district, state, finger_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "1234-5678-9012", 4, "Ramesh Kumar", "Sunita Kumar",
            "Rahul Kumar", "SBI-001234567", "9876543210",
            "123 Main Street", "Pune", "Maharashtra", "1"
        ))


def init_db():
    db = get_db()
    create_tables(db.cursor())
    insert_default_data(db.cursor())
    db.commit()
    db.close()


def get_all_users():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM users WHERE is_active=1 ORDER BY id"
    ).fetchall()
    db.close()
    return rows


def get_user_by_aadhar(aadhar_no):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE aadhar_no=?", (aadhar_no,)).fetchone()
    db.close()
    return row


def get_user_by_finger_id(finger_id):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE finger_id=?", (finger_id,)).fetchone()
    db.close()
    return row


def add_user(data):
    db = get_db()
    try:
        db.execute("""
            INSERT INTO users
            (aadhar_no, family_members, head_of_family, member2, member3,
             bank_ac, mobile, address, district, state, finger_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["aadhar_no"], data["family_members"], data["head_of_family"],
            data.get("member2", ""), data.get("member3", ""),
            data.get("bank_ac", ""), data["mobile"], data["address"],
            data["district"], data["state"], data.get("finger_id", "0")
        ))
        db.commit()
        return True, "User added successfully!"
    except sqlite3.IntegrityError:
        return False, "Aadhar number already exists!"
    finally:
        db.close()


def delete_user(user_id):
    db = get_db()
    try:
        db.execute("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
        db.commit()
        return True
    finally:
        db.close()


def get_all_commodities():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM commodities WHERE is_active=1 ORDER BY id"
    ).fetchall()
    db.close()
    return rows


def get_commodity_by_id(commodity_id):
    db = get_db()
    row = db.execute("SELECT * FROM commodities WHERE id=?", (commodity_id,)).fetchone()
    db.close()
    return row


def update_commodity_qty(commodity_id, new_qty):
    db = get_db()
    db.execute(
        "UPDATE commodities SET remaining_qty=?, updated_at=? WHERE id=?",
        (new_qty, datetime.now(), commodity_id)
    )
    db.commit()
    db.close()


def log_distribution(user_id, aadhar_no, commodity_id, commodity_name, qty, rate, total):
    db = get_db()
    db.execute("""
        INSERT INTO distribution_log
        (user_id, aadhar_no, commodity_id, commodity_name,
         qty_distributed, rate, total_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, aadhar_no, commodity_id, commodity_name, qty, rate, total))
    db.commit()
    db.close()


def get_distribution_logs():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM distribution_log ORDER BY distributed_at DESC"
    ).fetchall()
    db.close()
    return rows


def verify_admin(user_id, password):
    db = get_db()
    row = db.execute(
        "SELECT * FROM admins WHERE user_id=? AND password=?",
        (user_id, hash_password(password))
    ).fetchone()
    db.close()
    return row


def update_admin_password(user_id, new_password):
    db = get_db()
    db.execute(
        "UPDATE admins SET password=? WHERE user_id=?",
        (hash_password(new_password), user_id)
    )
    db.commit()
    db.close()


def get_dashboard_stats():
    db = get_db()
    total_users = db.execute(
        "SELECT COUNT(*) FROM users WHERE is_active=1"
    ).fetchone()[0]
    total_distributions = db.execute(
        "SELECT COUNT(*) FROM distribution_log"
    ).fetchone()[0]
    total_amount = db.execute(
        "SELECT COALESCE(SUM(total_amount), 0) FROM distribution_log"
    ).fetchone()[0]
    commodities = db.execute(
        "SELECT * FROM commodities WHERE is_active=1 ORDER BY id"
    ).fetchall()
    db.close()
    return {
        "total_users": total_users,
        "total_distributions": total_distributions,
        "total_amount": total_amount,
        "commodities": commodities,
    }


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
