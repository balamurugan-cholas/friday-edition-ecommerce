import sqlite3
from datetime import datetime

conn = sqlite3.connect("database.db")
c = conn.cursor()

# ------------------ Products Table ------------------
c.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    image TEXT,
    description TEXT,
    category TEXT,
    store TEXT
)
""")

# Example products (you can add more)
products = [
    ("Wireless Headphones", 59.99, "p1.jpg", "High-quality wireless headphones with noise cancellation.", "electronics", "Tech Store"),
    ("Smart Watch", 99.99, "p2.jpg", "Stay connected with this sleek smart watch.", "electronics", "Tech Store"),
    ("Bluetooth Speaker", 39.99, "p3.jpg", "Portable Bluetooth speaker with rich sound.", "electronics", "Tech Store"),
    ("Red Dress", 79.99, "dress1.jpg", "Elegant red dress perfect for any occasion.", "dress", "Fashion Hub"),
    ("Blue Dress", 69.99, "dress2.jpg", "Stylish blue dress for casual and formal wear.", "dress", "Fashion Hub"),
    ("Sneakers", 89.99, "sneakers1.jpg", "Comfortable sneakers for daily wear.", "sneakers", "Fashion Hub"),
    ("Slippers", 29.99, "slippers1.jpg", "Cozy slippers for indoor use.", "slippers", "Fashion Hub")
]

# Insert products
c.executemany("""
INSERT INTO products (name, price, image, description, category, store)
VALUES (?, ?, ?, ?, ?, ?)
""", products)

# ------------------ Partner Requests Table ------------------
c.execute("""
CREATE TABLE IF NOT EXISTS partner_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_name TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT
)
""")

# ------------------ Partners Table ------------------
c.execute("""
CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_name TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    phone TEXT,
    created_at TEXT,
    is_active INTEGER DEFAULT 1
)
""")

# ------------------ Cart Table ------------------
c.execute("""
CREATE TABLE IF NOT EXISTS cart (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER NOT NULL,
    quantity INTEGER DEFAULT 1,
    size TEXT,
    added_at TEXT DEFAULT (datetime('now'))
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS whatsapp_uploads (
    phone TEXT PRIMARY KEY,
    step TEXT,
    name TEXT,
    price REAL,
    description TEXT,
    category TEXT,
    image TEXT,
    store TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()
print("Database setup complete!")
