import sqlite3
import os

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'data', 'git_dashboard.db')

def migrate():
    if not os.path.exists(db_path):
        print("Database not found, nothing to migrate.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"Checking database at {db_path}...")

    # Check existing columns
    cursor.execute("PRAGMA table_info(repository)")
    columns = [column[1] for column in cursor.fetchall()]

    # Add 'category' if missing
    if 'category' not in columns:
        print("Adding 'category' column...")
        cursor.execute("ALTER TABLE repository ADD COLUMN category VARCHAR(50) DEFAULT 'General'")
    
    # Add 'run_command' if missing
    if 'run_command' not in columns:
        print("Adding 'run_command' column...")
        cursor.execute("ALTER TABLE repository ADD COLUMN run_command VARCHAR(255)")

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
