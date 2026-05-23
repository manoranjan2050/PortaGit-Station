import sqlite3
import os
from werkzeug.security import generate_password_hash

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'data', 'git_dashboard.db')

def migrate():
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Migrating to Auth & Theme system...")

    # 1. Create User table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(100) UNIQUE NOT NULL,
        password VARCHAR(200) NOT NULL,
        theme VARCHAR(20) DEFAULT 'light',
        accent_color VARCHAR(20) DEFAULT 'blue'
    )
    """)

    # 2. Check if default user exists, create if not
    cursor.execute("SELECT id FROM user WHERE username='admin'")
    if not cursor.fetchone():
        print("Creating default 'admin' user (password: admin)...")
        hashed_pw = generate_password_hash('admin')
        cursor.execute("INSERT INTO user (username, password) VALUES ('admin', ?)", (hashed_pw,))
        conn.commit()

    cursor.execute("SELECT id FROM user WHERE username='admin'")
    admin_id = cursor.fetchone()[0]

    # 3. Update Account table
    cursor.execute("PRAGMA table_info(account)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'user_id' not in columns:
        print("Adding 'user_id' to account table...")
        cursor.execute(f"ALTER TABLE account ADD COLUMN user_id INTEGER REFERENCES user(id) DEFAULT {admin_id}")

    # 4. Update Repository table
    cursor.execute("PRAGMA table_info(repository)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'user_id' not in columns:
        print("Adding 'user_id' to repository table...")
        cursor.execute(f"ALTER TABLE repository ADD COLUMN user_id INTEGER REFERENCES user(id) DEFAULT {admin_id}")

    conn.commit()
    conn.close()
    print("Migration successful! Use username 'admin' and password 'admin' to log in.")

if __name__ == "__main__":
    migrate()
