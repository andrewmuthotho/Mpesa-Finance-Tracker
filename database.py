# database.py

import sqlite3

DB_NAME = "transactions.db"

def create_connection(db_name=DB_NAME):
    """
    Create a SQLite database connection.
    """
    conn = sqlite3.connect(db_name)
    return conn

def create_table(conn):
    """
    Create the transactions table if it doesn't exist.
    Columns: receipt_no, date, time, description, amount, category.
    """
    create_sql = """
    CREATE TABLE IF NOT EXISTS transactions (
        receipt_no TEXT,
        date TEXT,
        time TEXT,
        description TEXT,
        amount REAL,
        category TEXT
    );
    """
    conn.execute(create_sql)
    conn.commit()

def insert_transaction(conn, tx):
    """
    Insert a single transaction (tuple) into the database.
    tx should be (receipt_no, date, time, description, amount, category).
    """
    sql = """
    INSERT INTO transactions (receipt_no, date, time, description, amount, category)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    conn.execute(sql, tx)
    conn.commit()

def transaction_exists(conn, receipt_no, date, amount):
    """
    Check if a transaction with given receipt_no, date, and amount already exists.
    This helps avoid duplicate uploads.
    """
    sql = "SELECT 1 FROM transactions WHERE receipt_no = ? AND date = ? AND amount = ?"
    cur = conn.execute(sql, (receipt_no, date, amount))
    return cur.fetchone() is not None

def get_transactions(conn, filter_str=None):
    """
    Query transactions, optionally filtering by a search string in description or receipt_no.
    Returns a list of rows.
    """
    if filter_str:
        like = f"%{filter_str}%"
        sql = "SELECT * FROM transactions WHERE description LIKE ? OR receipt_no LIKE ?"
        cur = conn.execute(sql, (like, like))
    else:
        sql = "SELECT * FROM transactions"
        cur = conn.execute(sql)
    return cur.fetchall()

def update_transaction_category(conn, receipt_no, new_category):
    """
    Update the category of a transaction by receipt_no.
    """
    sql = "UPDATE transactions SET category = ? WHERE receipt_no = ?"
    conn.execute(sql, (new_category, receipt_no))
    conn.commit()
