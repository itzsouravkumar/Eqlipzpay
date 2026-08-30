import sqlite3

def check_db():
    conn = sqlite3.connect("eqlipz.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables:", [t[0] for t in tables])
    conn.close()

if __name__ == "__main__":
    check_db()
