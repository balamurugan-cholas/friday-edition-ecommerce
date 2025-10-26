from flask import Flask, session
from routes.shop_routes import shop_bp, query_db   # Import blueprint

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Register Blueprint
app.register_blueprint(shop_bp)

@app.before_request
def clear_invalid_session():
    user_id = session.get("user_id")
    partner_id = session.get("partner_id")

    # Check normal user
    if user_id:
        user = query_db("SELECT id FROM users WHERE id=?", [user_id], one=True)
        if not user:
            session.pop("user_id", None)

    # Check partner
    if partner_id:
        partner = query_db("SELECT id FROM partners WHERE id=?", [partner_id], one=True)
        if not partner:
            session.pop("partner_id", None)

    # Don't clear session completely
    # Only clear if something is broken — not for guests
    # (This keeps 'cart' safe for non-logged-in users)


if __name__ == '__main__':
    app.run(debug=True)
