# SMI Home Automation System — Web App

A Flask-based web interface for the SMI Home Automation System.
Supports resident login, visitor PIN management, messaging, and activity logging.

---

## Quick Start (Local)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up environment variables
```bash
cp .env.example .env
# Edit .env and fill in your SECRET_KEY and RAPIDAPI_KEY
```

### 3. Run the app
```bash
python app.py
```
Visit http://localhost:5000

On first run, go to `/register` to create your first resident account.
After that, registration is restricted to logged-in residents only.

---

## Deploy to Render (Free Hosting)

1. Push this folder to a GitHub repo.
2. Go to https://render.com → New → Web Service.
3. Connect your repo.
4. Set these:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Add environment variables in the Render dashboard:
   - `SECRET_KEY` — generate one with: `python -c "import secrets; print(secrets.token_hex(32))"`
   - `RAPIDAPI_KEY` — your weather API key
6. Deploy. Render gives you a public URL.

---

## Security Notes

- Passwords are hashed using **Werkzeug's `generate_password_hash`** (bcrypt-based). Plain-text passwords are never stored.
- All SQL queries use **parameterized statements** — no SQL injection possible.
- The `SECRET_KEY` must be kept secret and should be a long random string in production.
- For production, switch from SQLite to **PostgreSQL** (add `psycopg2-binary` to requirements and update `DB_PATH`).

---

## Project Structure

```
has_web/
├── app.py               # Main Flask application
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── residence.db         # SQLite database (auto-created)
└── templates/
    ├── base.html        # Shared layout + sidebar
    ├── login.html       # Resident login
    ├── register.html    # Add new resident
    ├── dashboard.html   # Home dashboard
    ├── visitors.html    # Visitor management
    ├── visitor_portal.html   # Public PIN entry page
    ├── visitor_welcome.html  # Shown after successful PIN
    ├── messages.html    # Visitor messages inbox
    ├── activity_log.html     # Check-in history
    └── users.html       # Resident management
```
