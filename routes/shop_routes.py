from flask import (
    Blueprint, render_template, request,
    redirect, url_for, session, flash, g, jsonify, Response
)
import sqlite3
from datetime import datetime, time
from werkzeug.security import generate_password_hash, check_password_hash
import string, random
import requests
from werkzeug.utils import secure_filename
import os
from functools import wraps
from twilio.twiml.messaging_response import MessagingResponse

shop_bp = Blueprint('shop', __name__)
DATABASE = "database.db"

UPLOAD_FOLDER = "static/images"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# In-memory store for partner product info (later move to DB)
whatsapp_sessions = {}

WHATSAPP_CATEGORIES = ["electronics", "fashion", "sports", "books", "toys"]

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------ Database Helpers ------------------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def query_db(query, args=(), one=False, commit=False):
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    if commit:
        conn.commit()  # commit changes
    if query.strip().upper().startswith("SELECT"):
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return (rows[0] if rows else None) if one else rows
    else:
        cur.close()
        conn.close()
        return None


def execute_db(query, args=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    return cur.lastrowid

@shop_bp.teardown_app_request
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# ------------------ Size Options ------------------
SIZE_OPTIONS = {
    "dress": ["S", "M", "L", "XL", "XXL"],
    "sneakers": ["6", "7", "8", "9", "10"],
    "shoes": ["6", "7", "8", "9", "10"],
    "slippers": ["6", "7", "8", "9", "10"]
}

# ----------------- SEARCH_SYNONYMS -----------------
SEARCH_SYNONYMS = {
    "tshirt":    ["tee", "hoodie", "shirt", "innerwear", "top", "casual wear"],
    "shirt":     ["formal", "casual", "button-down", "polo", "blouse"],
    "pant":      ["jeans", "trouser", "cotton", "formal", "chinos", "leggings"],
    "jeans":     ["denim", "skinny", "slim", "bootcut", "trousers"],
    "dress":     ["gown", "frock", "evening wear", "maxi", "mini", "cocktail"],
    "skirt":     ["mini", "midi", "maxi", "pencil", "pleated"],
    "shoe":      ["sneakers", "boots", "loafers", "heels", "sandals", "flip-flops"],
    "sneakers":  ["shoe", "trainers", "running shoes", "sports shoes"],
    "watch":     ["wristwatch", "smartwatch", "analog watch", "digital watch"],
    "bag":       ["backpack", "handbag", "tote", "purse", "clutch"],
    "cap":       ["hat", "beanie", "snapback", "baseball cap"],
    "mobile":    ["smartphone", "cellphone", "iphone", "android"],
    "laptop":    ["notebook", "macbook", "ultrabook", "chromebook"],
    "tablet":    ["ipad", "android tablet", "surface"],
    "headphones":["earphones", "earbuds", "headset", "wireless headphones"],
    "camera":    ["dslr", "mirrorless", "action camera", "point-and-shoot"],
    "tv":        ["television", "led tv", "oled", "smart tv"],
    "sports":    ["fitness", "gym", "yoga", "running", "outdoor"],
    "beauty":    ["makeup", "skincare", "cosmetics", "haircare", "perfume"],
    "toy":       ["kids toy", "puzzle", "lego", "action figure", "doll"],
    "jewelry":   ["necklace", "bracelet", "earrings", "ring", "bangle"],
    "perfume":   ["cologne", "fragrance", "scent", "eau de toilette"],
    "home":      ["furniture", "decor", "kitchen", "appliances", "bedding"],
    "watchband": ["strap", "leather strap", "metal strap", "silicone strap"]
}

def reset_whatsapp_product_session():
    session["whatsapp_product"] = {
        "step": "name",  # start with name
        "data": {}
    }

def expand_keywords(q: str):
    q_lower = q.lower()
    extras = []
    for key, synonyms in SEARCH_SYNONYMS.items():
        if key in q_lower:
            extras.extend(synonyms)
    return extras

def partner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        partner_id = session.get('partner_id')
        if not partner_id:
            flash("Please login first.", "danger")
            return redirect(url_for('shop.partner_login'))

        # Check if partner still exists and is active
        partner = query_db("SELECT * FROM partners WHERE id=? AND is_active=1", [partner_id], one=True)
        if not partner:
            session.clear()  # Clear any leftover session
            flash("Your account has been removed by admin.", "danger")
            return redirect(url_for('shop.partner_login'))

        return f(*args, **kwargs)
    return decorated_function

# ------------------ Routes ------------------
@shop_bp.route('/')
def home():
    all_products = query_db("SELECT * FROM products ORDER BY id DESC")
    all_shops = sorted({p["store"] for p in all_products})
    hero_products = all_products[:4]  # Top 4 latest products for hero cards
    # Optional: You can create a separate table for hero slides if needed
    hero_slides = all_products[:3]  # First 3 products as carousel slides
    return render_template("home.html",
                           all_products=all_products,
                           all_shops=all_shops,
                           hero_products=hero_products,
                           hero_slides=hero_slides)

@shop_bp.route('/search-suggestions')
def search_suggestions():
    q = request.args.get('query', '').strip()
    results = []
    if q:
        keywords = [q] + expand_keywords(q)
        clauses = []
        params = []
        for k in keywords:
            clauses.append("(name LIKE ? OR description LIKE ? OR category LIKE ?)")
            params.extend([f"%{k}%"] * 3)
        sql = f"""
            SELECT id, name FROM products
            WHERE {" OR ".join(clauses)}
            LIMIT 5
        """
        rows = query_db(sql, params)
        results = [{"id": r["id"], "name": r["name"]} for r in rows]
    return jsonify(results)


@shop_bp.route('/search')
def search():
    q = request.args.get('q', '').strip()
    products = []
    if q:
        keywords = [q] + expand_keywords(q)
        clauses = []
        params = []
        for k in keywords:
            clauses.append("(name LIKE ? OR description LIKE ? OR category LIKE ?)")
            params.extend([f"%{k}%"] * 3)
        sql = f"""
            SELECT * FROM products
            WHERE {" OR ".join(clauses)}
            ORDER BY id DESC
        """
        products = query_db(sql, params)
    return render_template('search_results.html', products=products, query=q)


@shop_bp.route('/product/<int:product_id>')
def product_page(product_id):
    product = query_db("SELECT * FROM products WHERE id=?", [product_id], one=True)
    if not product:
        return "Product not found", 404
    related = query_db("SELECT * FROM products WHERE category=? AND id!=?", [product["category"], product_id])
    same_store = query_db("SELECT * FROM products WHERE store=? AND id!=?", [product["store"], product_id])
    all_shops = sorted({p["store"] for p in query_db("SELECT * FROM products")})
    return render_template('product.html',
                           product=product,
                           related_products=related,
                           store_products=same_store,
                           all_shops=all_shops)

# ------------------ Cart ------------------
def get_cart_items():
    cart = session.get("cart", [])
    cart_items = []
    subtotal = 0
    updated_cart = []
    
    for item in cart:
        prod = query_db("SELECT * FROM products WHERE id=?", [item["id"]], one=True)
        if not prod:
            continue  # Skip if product deleted
        qty = item.get("quantity", 1)
        subtotal += prod["price"] * qty
        updated_cart.append(item)
        cart_items.append({**item, "image": prod["image"], "shop_name": prod["store"]})
    
    # Update session cart to remove deleted products
    session['cart'] = updated_cart
    session.modified = True
    return cart_items, subtotal

def get_cart_quantity():
    return sum(item.get("quantity", 0) for item in session.get("cart", []))

@shop_bp.route('/cart')
def view_cart():
    cart_items, subtotal = get_cart_items()
    products = query_db("SELECT * FROM products")
    all_shops = sorted({p["store"] for p in products})
    return render_template("cart.html",
                           cart_items=cart_items,
                           subtotal=subtotal,
                           shipping=10,
                           all_products=products,
                           all_shops=all_shops)

@shop_bp.route('/add-to-cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = query_db("SELECT * FROM products WHERE id=?", [product_id], one=True)
    if not product:
        flash("Product not found.", "danger")
        return redirect(request.referrer or url_for('shop.home'))
    try:
        quantity = max(1, int(request.form.get('quantity', 1)))
    except ValueError:
        quantity = 1
    size = request.form.get("size")
    valid_sizes = SIZE_OPTIONS.get(product["category"])
    if valid_sizes and size not in valid_sizes:
        flash("Invalid size selected.", "danger")
        return redirect(request.referrer or url_for('shop.product_page', product_id=product_id))
    if not valid_sizes:
        size = None
    cart = session.setdefault("cart", [])
    for item in cart:
        if item["id"] == product["id"] and item.get("size") == size:
            item["quantity"] += quantity
            break
    else:
        cart.append({"id": product["id"], "name": product["name"], "price": product["price"],
                     "quantity": quantity, "size": size})
    session.modified = True
    flash(f"Added {quantity} × {product['name']} to cart!", "success")
    return redirect(request.referrer or url_for('shop.product_page', product_id=product_id))

# ------------------ Clear Cart ------------------
@shop_bp.route('/clear-cart', methods=['POST'])
def clear_cart():
    session['cart'] = []
    session.modified = True
    return jsonify({"status": "success", "cart_count": 0})

# ------------------ Update Cart Quantity ------------------
@shop_bp.route('/update-cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    data = request.get_json()
    quantity = int(data.get('quantity', 1))
    cart = session.get('cart', [])
    item_total = 0
    subtotal = 0

    for item in cart[:]:  # Copy of list for safe removal
        if item['id'] == product_id:
            if quantity <= 0:
                cart.remove(item)
            else:
                item['quantity'] = quantity
                item_total = round(item['quantity'] * item['price'], 2)  # ✅ Rounded

    # Recalculate subtotal
    for item in cart:
        subtotal += item['quantity'] * item['price']

    subtotal = round(subtotal, 2)  # ✅ Rounded subtotal

    session['cart'] = cart
    session.modified = True

    return jsonify({
        "success": True,
        "cart_quantity": get_cart_quantity(),
        "item_total": item_total,
        "subtotal": subtotal
    })

# ------------------ Remove Item from Cart ------------------
@shop_bp.route('/remove-from-cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = session.get('cart', [])
    cart = [item for item in cart if item['id'] != product_id]

    subtotal = sum(item['quantity'] * item['price'] for item in cart)
    session['cart'] = cart
    session.modified = True

    return jsonify({
        "success": True,
        "cart_quantity": get_cart_quantity(),
        "subtotal": subtotal
    })


# ------------------ Category & Shop Pages ------------------
@shop_bp.route('/category/<string:category_name>')
def category_page(category_name):
    filtered = query_db("SELECT * FROM products WHERE LOWER(category)=?", [category_name.lower()])
    all_shops = sorted({p["store"] for p in query_db("SELECT * FROM products")})
    return render_template('category.html',
                           category_name=category_name.title(),
                           products=filtered,
                           all_shops=all_shops)

@shop_bp.route('/shop/<string:shop_name>')
def shop_page(shop_name):
    filter_cat = request.args.get("filter_category")
    store_products = query_db("SELECT * FROM products WHERE LOWER(store)=?", [shop_name.lower()])
    if filter_cat:
        store_products = [p for p in store_products if p["category"].lower() == filter_cat.lower()]
    store_categories = sorted({p["category"] for p in query_db("SELECT * FROM products WHERE LOWER(store)=?", [shop_name.lower()])})
    all_shops = sorted({p["store"] for p in query_db("SELECT * FROM products")})
    return render_template('shop.html',
                           shop_name=shop_name.title(),
                           store_products=store_products,
                           store_categories=store_categories,
                           all_shops=all_shops)

# ------------------ Partner Registration ------------------
@shop_bp.route('/partner/register', methods=['GET', 'POST'])
def partner_register():
    if request.method == 'POST':
        shop_name = request.form.get('shop_name', '').strip()
        owner_name = request.form.get('owner_name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()

        # Check required fields
        if not shop_name or not owner_name or not phone or not email:
            flash("Please fill all required fields!", "danger")
            return redirect(url_for('shop.partner_register'))

        # Check if email already exists in partners table
        existing_partner = query_db("SELECT * FROM partners WHERE email=?", [email], one=True)
        if existing_partner:
            flash("Email already exists! Please use a different email.", "danger")
            return redirect(url_for('shop.partner_register'))

        # Also check if a pending request already exists
        existing_request = query_db("SELECT * FROM partner_requests WHERE email=? AND status='pending'", [email], one=True)
        if existing_request:
            flash("A request with this email is already pending!", "danger")
            return redirect(url_for('shop.partner_register'))

        # Insert new partner request
        execute_db(
            "INSERT INTO partner_requests (shop_name, owner_name, phone, email, status, created_at) VALUES (?,?,?,?,?,?)",
            [shop_name, owner_name, phone, email, "pending", datetime.now()]
        )
        flash("Request submitted! We'll call you to verify.", "success")
        return redirect(url_for('shop.home'))

    return render_template('partner_register.html')


# ------------------ Partner Login / Dashboard ------------------
@shop_bp.route('/partner/login', methods=['GET', 'POST'])
def partner_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        if not email or not password:
            flash("Please enter email and password", "danger")
            return redirect(url_for('shop.partner_login'))

        # Only allow active partners to login
        partner = query_db("SELECT * FROM partners WHERE email=? AND is_active=1", [email], one=True)
        if partner and check_password_hash(partner['password'], password):
            session['partner_id'] = partner['id']
            session['partner_name'] = partner['owner_name']
            session['partner_shop'] = partner['shop_name']
            flash(f"Welcome, {partner['owner_name']}!", "success")
            return redirect(url_for('shop.partner_dashboard'))
        else:
            flash("Invalid email or password, or your account is inactive.", "danger")
            return redirect(url_for('shop.partner_login'))

    return render_template('partner_login.html')


@shop_bp.route('/partner/dashboard')
@partner_required
def partner_dashboard():
    partner_id = session['partner_id']
    shop_name = session['partner_shop']
    products = query_db("SELECT * FROM products WHERE LOWER(store)=?", [shop_name.lower()])
    return render_template('partner_dashboard.html', products=products, partner_name=session['partner_name'])


@shop_bp.route('/partner/logout')
def partner_logout():
    session.pop('partner_id', None)
    session.pop('partner_name', None)
    session.pop('partner_shop', None)
    session['partner_logged_out'] = True
    flash("Logged out successfully.", "success")
    return redirect(url_for('shop.partner_login'))


@shop_bp.route('/partner/add-product', methods=['POST'])
@partner_required
def add_product():
    name = request.form.get("name", "").strip()
    price = request.form.get("price", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    store = session.get("partner_shop")

    if not name or not price or not category or not store:
        flash("Please fill all required fields!", "danger")
        return redirect(url_for("shop.partner_dashboard"))

    image_file = request.files.get("image")
    image_name = None
    if image_file and allowed_file(image_file.filename):
        filename = secure_filename(image_file.filename)
        image_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        image_path = os.path.join(UPLOAD_FOLDER, image_name)
        image_file.save(image_path)
    else:
        flash("Please upload a valid image file.", "danger")
        return redirect(url_for("shop.partner_dashboard"))

    try:
        execute_db("""
            INSERT INTO products (name, price, image, description, category, store)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [name, float(price), image_name, description, category, store])
        flash("Product added successfully!", "success")
    except Exception as e:
        flash(f"Error adding product: {e}", "danger")

    return redirect(url_for("shop.partner_dashboard"))


# ---- Edit Product ----
@shop_bp.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
@partner_required
def edit_product(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    if not product:
        flash("Product not found", "danger")
        return redirect(url_for('shop.partner_dashboard'))

    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        category = request.form['category']
        description = request.form['description']
        db.execute("""
            UPDATE products
            SET name=?, price=?, category=?, description=?
            WHERE id=?
        """, (name, price, category, description, product_id))
        db.commit()
        flash("Product updated successfully!", "success")
        return redirect(url_for('shop.partner_dashboard'))

    return render_template('edit_product.html', product=product)


# ---- Delete Product ----
@shop_bp.route('/product/<int:product_id>/delete', methods=['POST'])
@partner_required
def delete_product(product_id):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    flash("Product deleted successfully!", "success")
    return redirect(url_for('shop.partner_dashboard'))


# ------------------ Admin Routes ------------------
def generate_random_password(length=8):
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(chars) for _ in range(length))

@shop_bp.route('/admin/partner-requests')
def admin_partner_requests():
    # Fetch both pending and approved partners, but exclude deleted
    requests = query_db("""
        SELECT id, shop_name as name, email, phone, '' as message, status, created_at
        FROM partner_requests
        WHERE status IN ('pending', 'approved')
        ORDER BY created_at DESC
    """)
    return render_template('adminpage.html', partner_requests=requests)

@shop_bp.route('/admin/handle-request/<int:request_id>', methods=['POST'])
def handle_request(request_id):
    # Fetch partner request
    req = query_db("SELECT * FROM partner_requests WHERE id=?", [request_id], one=True)
    if not req:
        return jsonify({"success": False, "error": "Request not found"})

    # Generate random password
    password = generate_random_password()
    hashed_pw = generate_password_hash(password)

    print(f"Generated credentials for {req['email']}: {password}")

    # Insert into partners table and get new partner_id
    partner_id = execute_db(
        "INSERT INTO partners (shop_name, owner_name, email, password, phone, created_at, is_active) VALUES (?,?,?,?,?,?,?)",
        [req['shop_name'], req['owner_name'], req['email'], hashed_pw, req['phone'], datetime.now(), 1]
    )

    # Update request status
    execute_db("UPDATE partner_requests SET status=? WHERE id=?", ["approved", request_id])

    # Send email via Formspree (optional)
    formspree_url = "https://formspree.io/f/xwprvoqy"
    data = {
        "shop_name": req['shop_name'],
        "owner_name": req['owner_name'],
        "email": req['email'],
        "password": password
    }
    try:
        requests.post(formspree_url, data=data)
    except:
        pass  # ignore errors

    # ✅ Return partner_id to frontend
    return jsonify({"success": True, "partner_id": partner_id})


@shop_bp.route('/admin/delete-request/<int:request_id>', methods=['POST'])
def delete_request(request_id):
    execute_db("UPDATE partner_requests SET status='deleted' WHERE id=?", [request_id])
    return jsonify({"success": True})

@shop_bp.route('/admin/partner/<int:partner_id>/delete', methods=['POST'])
def admin_delete_partner(partner_id):
    print("Delete partner route hit:", partner_id)
    #if "admin_id" not in session:   # Protect this route
        #print("Admin session:", session.get("admin_id"))
        #return jsonify({"success": False, "error": "Unauthorized"}), 401

    db = get_db()

    # Find partner shop name
    partner = db.execute(
        "SELECT shop_name FROM partners WHERE id = ?", (partner_id,)
    ).fetchone()

    if not partner:
        return jsonify({"success": False, "error": "Partner not found"}), 404

    shop_name = partner['shop_name']

    try:
        # Delete cart items for this partner's products
        db.execute("""
            DELETE FROM cart
            WHERE product_id IN (
                SELECT id FROM products WHERE store = ?
            )
        """, (shop_name,))

        # Delete products
        db.execute("DELETE FROM products WHERE store = ?", (shop_name,))

        # Delete partner account
        db.execute("DELETE FROM partners WHERE id = ?", (partner_id,))

        db.commit()
        return jsonify({"success": True, "message": f"Partner '{shop_name}' deleted"})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)})

@shop_bp.route('/whatsapp', methods=['POST'])
def whatsapp():
    from twilio.twiml.messaging_response import MessagingResponse

    incoming_msg = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '').replace('whatsapp:', '')

    resp = MessagingResponse()
    msg = resp.message()

    # Fetch partner as dict
    partner = query_db("SELECT * FROM partners WHERE phone=?", [from_number], one=True)
    if not partner:
        msg.body("You're not registered as a partner. Please register first.")
        return str(resp)

    # -------- Restart session if partner types 'restart' --------
    if incoming_msg.lower() == "restart":
        whatsapp_sessions[from_number] = {
            "step": "name",
            "data": {
                "name": None,
                "price": None,
                "description": None,
                "category": None,
                "image": None
            }
        }
        msg.body("🔄 Session restarted! Let's start over.\nPlease send the product name.")
        return str(resp)

    # Initialize session if not exists
    if from_number not in whatsapp_sessions:
        whatsapp_sessions[from_number] = {
            "step": "name",
            "data": {
                "name": None,
                "price": None,
                "description": None,
                "category": None,
                "image": None
            }
        }

    session_data = whatsapp_sessions[from_number]

    # ---------------- Step machine ----------------
    if session_data["step"] == "name":
        session_data["data"]["name"] = incoming_msg
        session_data["step"] = "price"
        msg.body("✅ Got it! Now send the product price (numbers only).")

    elif session_data["step"] == "price":
        try:
            price = float(incoming_msg)
            session_data["data"]["price"] = price
            session_data["step"] = "description"
            msg.body("✅ Great! Now send the product description.")
        except ValueError:
            msg.body("⚠️ Please send a valid number for the price.")

    elif session_data["step"] == "description":
        session_data["data"]["description"] = incoming_msg
        session_data["step"] = "category"
        msg.body(f"✅ Description noted! Send the category. Choose from: {', '.join(WHATSAPP_CATEGORIES)}")

    elif session_data["step"] == "category":
        # Normalize input and categories for matching
        matched_category = None
        for cat in WHATSAPP_CATEGORIES:
            if incoming_msg.lower() == cat.lower():
                matched_category = cat  # store the original category name (correct capitalization)
                break

        if matched_category:
            session_data["data"]["category"] = matched_category
            session_data["step"] = "image"
            msg.body("✅ Category accepted! Finally, send the product image as attachment.")
        else:
            msg.body(f"⚠️ Invalid category. Choose from: {', '.join(WHATSAPP_CATEGORIES)}")

    elif session_data["step"] == "image":
        num_media = int(request.values.get('NumMedia', 0))
        if num_media > 0:
            image_url = request.values.get('MediaUrl0')
            session_data["data"]["image"] = image_url

            # Insert into database
            data = session_data["data"]
            store_name = partner["name"] if isinstance(partner, dict) else partner[1]

            query_db(
                "INSERT INTO products (name, price, description, category, store, image) VALUES (?, ?, ?, ?, ?, ?)",
                [data["name"], data["price"], data["description"], data["category"], store_name, data["image"]],
                commit=True
            )

            msg.body("✅ Product uploaded successfully with your image!")
            # Clear session
            whatsapp_sessions.pop(from_number, None)
        else:
            msg.body("⚠️ Please send the product image as an attachment from your device.")

    # Save session
    whatsapp_sessions[from_number] = session_data
    return str(resp)

