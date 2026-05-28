import sqlite3
import random
import datetime as dt
import os
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__, template_folder=".")
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")

# On Vercel, the filesystem is read-only. We must use the /tmp directory for the SQLite database.
if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
    DB_PATH = "/tmp/residence.db"
else:
    DB_PATH = os.environ.get("DB_PATH", "residence.db")



# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name  TEXT NOT NULL,
            email      TEXT UNIQUE NOT NULL,
            username   TEXT UNIQUE NOT NULL,
            password   TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS visitors (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT NOT NULL,
            mobile_number       TEXT NOT NULL,
            appointment_creator TEXT NOT NULL,
            pin                 INTEGER NOT NULL,
            timestamp           TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS visitors_messages (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_name TEXT NOT NULL,
            message      TEXT NOT NULL,
            timestamp    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activities_log (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_name      TEXT NOT NULL,
            visitor_login_time TEXT NOT NULL,
            username          TEXT NOT NULL,
            user_login_time   TEXT NOT NULL
        );
    """)
    
    # Seed a demo user if the database is newly initialized
    cur.execute("SELECT 1 FROM users LIMIT 1")
    if not cur.fetchone():
        hashed_password = generate_password_hash("demo1234")
        cur.execute(
            "INSERT INTO users (first_name, last_name, email, username, password) VALUES (?, ?, ?, ?, ?)",
            ("Demo", "User", "demo@example.com", "demo", hashed_password)
        )
    conn.commit()
    conn.close()


# Initialize database on the first request to prevent write errors during Vercel's import phase
@app.before_request
def initialize_database():
    if not getattr(app, "_database_initialized", False):
        init_db()
        app._database_initialized = True


def pin_generator():
    return random.randint(1000, 9999)


# ── Auth decorators ───────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Weather helper ────────────────────────────────────────────────────────────

def get_weather():
    api_key = os.environ.get("RAPIDAPI_KEY")
    if not api_key:
        return None
    try:
        url = "https://open-weather13.p.rapidapi.com/city/Lagos, Nigeria/EN"
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "open-weather13.p.rapidapi.com"
        }
        resp = requests.get(url, headers=headers, timeout=5)
        data = resp.json()
        return {
            "temp": round(data["main"]["temp"]),
            "desc": data["weather"][0]["description"].capitalize(),
            "icon": data["weather"][0]["icon"],
        }
    except Exception:
        return None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"]    = user["id"]
            session["username"]   = user["username"]
            session["first_name"] = user["first_name"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """First-run registration — accessible only if no users exist yet."""
    conn = get_db()
    has_users = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    conn.close()
    if has_users and "user_id" not in session:
        flash("Registration is invite-only. Please log in.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name  = request.form.get("last_name", "").strip()
        email      = request.form.get("email", "").strip()
        username   = request.form.get("username", "").strip()
        password   = request.form.get("password", "")
        confirm    = request.form.get("confirm_password", "")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")
        hashed = generate_password_hash(password)
        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO users (first_name, last_name, email, username, password) VALUES (?,?,?,?,?)",
                (first_name, last_name, email, username, hashed)
            )
            conn.commit()
            conn.close()
            flash("User registered successfully!", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or email already exists.", "error")
    return render_template("register.html")


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    visitor_count = conn.execute("SELECT COUNT(*) FROM visitors").fetchone()[0]
    message_count = conn.execute("SELECT COUNT(*) FROM visitors_messages").fetchone()[0]
    user_count    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    log_count     = conn.execute("SELECT COUNT(*) FROM activities_log").fetchone()[0]
    recent_logs   = conn.execute(
        "SELECT * FROM activities_log ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()
    weather = get_weather()
    now = dt.datetime.now()
    hour = now.hour
    if 0 <= hour < 12:   greeting = "Good Morning"
    elif hour < 16:      greeting = "Good Afternoon"
    elif hour < 22:      greeting = "Good Evening"
    else:                greeting = "Good Night"
    return render_template("dashboard.html",
        visitor_count=visitor_count,
        message_count=message_count,
        user_count=user_count,
        log_count=log_count,
        recent_logs=recent_logs,
        weather=weather,
        greeting=greeting,
        now=now,
    )


# ── Visitors ──────────────────────────────────────────────────────────────────

@app.route("/visitors")
@login_required
def visitors():
    conn = get_db()
    all_visitors = conn.execute("SELECT * FROM visitors ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("visitors.html", visitors=all_visitors)


@app.route("/visitors/create", methods=["POST"])
@login_required
def create_visitor():
    name          = request.form.get("name", "").strip()
    mobile_number = request.form.get("mobile_number", "").strip()
    if not name or not mobile_number:
        flash("Name and mobile number are required.", "error")
        return redirect(url_for("visitors"))
    pin       = pin_generator()
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    creator   = session["first_name"]
    conn = get_db()
    conn.execute(
        "INSERT INTO visitors (name, mobile_number, appointment_creator, pin, timestamp) VALUES (?,?,?,?,?)",
        (name, mobile_number, creator, pin, timestamp)
    )
    conn.commit()
    conn.close()
    flash(f"Visitor PIN for {name} is: {pin}", "success")
    return redirect(url_for("visitors"))


@app.route("/visitors/delete/<int:vid>", methods=["POST"])
@login_required
def delete_visitor(vid):
    conn = get_db()
    conn.execute("DELETE FROM visitors WHERE id = ?", (vid,))
    conn.commit()
    conn.close()
    flash("Visitor deleted.", "success")
    return redirect(url_for("visitors"))


# ── Visitor portal (public PIN login) ─────────────────────────────────────────

@app.route("/visitor-portal", methods=["GET", "POST"])
def visitor_portal():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "login":
            try:
                pin = int(request.form.get("pin", 0))
            except ValueError:
                flash("PIN must be a number.", "error")
                return render_template("visitor_portal.html")
            conn = get_db()
            visitor = conn.execute(
                "SELECT * FROM visitors WHERE pin = ?", (pin,)
            ).fetchone()
            if visitor:
                timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    "INSERT INTO activities_log (visitor_name, visitor_login_time, username, user_login_time) VALUES (?,?,?,?)",
                    (visitor["name"], timestamp, visitor["appointment_creator"], timestamp)
                )
                conn.commit()
                conn.close()
                return render_template("visitor_welcome.html", visitor=visitor)
            conn.close()
            flash("Invalid PIN. Please try again or contact the resident.", "error")

        elif action == "message":
            visitor_name = request.form.get("visitor_name", "").strip()
            message      = request.form.get("message", "").strip()
            if visitor_name and message:
                timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn = get_db()
                conn.execute(
                    "INSERT INTO visitors_messages (visitor_name, message, timestamp) VALUES (?,?,?)",
                    (visitor_name, message, timestamp)
                )
                conn.commit()
                conn.close()
                flash("Your message has been sent to the residents.", "success")
            else:
                flash("Please fill in your name and message.", "error")

    return render_template("visitor_portal.html")


# ── Messages ──────────────────────────────────────────────────────────────────

@app.route("/messages")
@login_required
def messages():
    conn = get_db()
    all_messages = conn.execute(
        "SELECT * FROM visitors_messages ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template("messages.html", messages=all_messages)


@app.route("/messages/clear", methods=["POST"])
@login_required
def clear_messages():
    conn = get_db()
    conn.execute("DELETE FROM visitors_messages")
    conn.commit()
    conn.close()
    flash("All messages cleared.", "success")
    return redirect(url_for("messages"))


# ── Activity Log ──────────────────────────────────────────────────────────────

@app.route("/activity-log")
@login_required
def activity_log():
    conn = get_db()
    logs = conn.execute(
        "SELECT * FROM activities_log ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template("activity_log.html", logs=logs)


# ── Users ─────────────────────────────────────────────────────────────────────

@app.route("/users")
@login_required
def users():
    conn = get_db()
    all_users = conn.execute(
        "SELECT id, first_name, last_name, email, username FROM users"
    ).fetchall()
    conn.close()
    return render_template("users.html", users=all_users)


@app.route("/users/delete/<int:uid>", methods=["POST"])
@login_required
def delete_user(uid):
    if uid == session["user_id"]:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("users"))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()
    conn.close()
    flash("User deleted.", "success")
    return redirect(url_for("users"))


# ── Global Exception Handler ──────────────────────────────────────────────────

@app.errorhandler(Exception)
def handle_exception(e):
    from werkzeug.exceptions import HTTPException
    import traceback
    
    # Pass through standard Flask HTTP exceptions (like 404, 405, redirects)
    if isinstance(e, HTTPException):
        return e
        
    # Render a beautiful debug traceback directly to the page for any code crashes (500s)
    tb = traceback.format_exc()
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Application Error</title>
        <style>
            body {{ font-family: monospace; padding: 30px; background: #0b0f0e; color: #e8f0ef; line-height: 1.6; }}
            .card {{ background: #131918; border: 1px solid #243030; border-radius: 12px; padding: 30px; max-width: 800px; margin: 40px auto; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }}
            h1 {{ color: #ff4d6d; font-family: sans-serif; font-size: 1.8rem; margin-top: 0; }}
            pre {{ background: #1a2120; border: 1px solid #243030; padding: 20px; border-radius: 8px; overflow-x: auto; color: #e8f0ef; font-size: 0.85rem; }}
            p {{ color: #6b8a85; font-size: 0.9rem; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Application Exception Encountered</h1>
            <p>An unexpected error occurred during request execution. Below is the technical traceback to help us resolve the issue:</p>
            <pre>{tb}</pre>
            <p style="margin-top: 20px; font-size: 0.8rem; color: #00e5a0;">Please copy and paste the traceback above to the assistant so we can solve the issue immediately.</p>
        </div>
    </body>
    </html>
    """, 500


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
