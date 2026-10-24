"""Create a sample v1 database: python3 data/make_v1.py PATH"""
import sqlite3, sys

CONTACTS = [(1, "Yamada Taro", "taro@example.com", "vip,tokyo"), (2, "Suzuki Hanako", "hanako@example.com", "tokyo"),
            (3, "Tanaka Ichiro", None, None)]
NOTES = [(1, 1, "met at expo"), (2, 1, "sent quote"), (3, 3, "call back")]


def build(path, contacts=CONTACTS, notes=NOTES):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE contacts (id INTEGER PRIMARY KEY, full_name TEXT, email TEXT, tags TEXT);
        CREATE TABLE notes (id INTEGER PRIMARY KEY, contact_id INTEGER, body TEXT);
        PRAGMA user_version = 1;""")
    con.executemany("INSERT INTO contacts VALUES (?,?,?,?)", contacts)
    con.executemany("INSERT INTO notes VALUES (?,?,?)", notes)
    con.commit()
    con.close()


if __name__ == "__main__":
    build(sys.argv[1])
