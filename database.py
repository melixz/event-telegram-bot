import sqlite3


def get_db_connection():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        selected_greetings TEXT,
        last_choice_date TEXT
    )
    """)
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def add_user(user_id):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO users (user_id, selected_greetings, last_choice_date) VALUES (?, ?, ?)",
        (user_id, "", ""),
    )
    conn.commit()
    conn.close()


def update_user(user_id, selected_greetings, last_choice_date):
    conn = get_db_connection()
    conn.execute(
        """
        UPDATE users 
        SET selected_greetings = ?, last_choice_date = ?
        WHERE user_id = ?
        """,
        (selected_greetings, last_choice_date, user_id),
    )
    conn.commit()
    conn.close()


def get_all_user_ids():
    conn = get_db_connection()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    return [u["user_id"] for u in users]
