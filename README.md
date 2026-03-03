# THREADLINE

A custom e-commerce web app built with Flask. Customers browse products, place orders with payment screenshot uploads, and track their order status. Admins manage everything through a dashboard.

---

## Features

**Customer-facing**
- Browse design catalog with multi-photo carousel
- Place orders with PhonePe payment screenshot upload
- Real-time 5-stage order tracking by phone number
- Order confirmation page with PDF invoice download
- WhatsApp contact button

**Admin dashboard** (`/admin`)
- View and manage all active, completed, and cancelled orders
- Update order status — customer receives an email on every change
- Add, edit, and delete designs with multiple photos
- Toggle stock availability and track quantities
- Export all orders to Excel
- Sales analytics charts
- Configure PhonePe payment details
- Configure Resend email settings
- Send test email to verify configuration
- Change admin password

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| Database | SQLite (`database.db`) |
| ORM | Flask-SQLAlchemy |
| Forms / CSRF | Flask-WTF |
| Email | Resend API (HTTP) |
| PDF | ReportLab |
| Excel | openpyxl |
| Server | Gunicorn |

---

## Project Structure

```
threadline/
├── app.py                  # All routes and application logic
├── requirements.txt
├── database.db             # SQLite database (auto-created on first run)
├── static/
│   └── uploads/            # Design images and payment screenshots
└── templates/
    ├── home.html           # Public storefront
    ├── order.html          # Order form
    ├── success.html        # Order confirmation
    ├── track_order.html    # Customer order tracking
    ├── login.html          # Admin login
    ├── dashboard.html      # Admin dashboard
    ├── add_design.html
    ├── edit_design.html
    ├── change_password.html
    ├── sales_report.html
    └── 404.html            # Handles 404 / 500 / 413 errors
```

---

## Local Setup

```bash
# 1. Clone
git clone https://github.com/yourusername/threadline.git
cd threadline

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
FLASK_DEBUG=1 python app.py
```

Open `http://localhost:5000`

Default admin login: go to `/admin` — password is `admin123`.  
Change it immediately after first login at `/change_password`.

---

## Deployment (Render)

1. Push the repository to GitHub
2. Create a new **Web Service** on [render.com](https://render.com) and connect the repo
3. Set the following:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. Add one environment variable:

| Variable | Value |
|---|---|
| `SECRET_KEY` | Any long random string |

> **Note:** Render's free plan has an ephemeral filesystem — `database.db` and uploaded images reset on every redeploy or server restart. For persistent storage, use a paid plan with a disk add-on.

---

## Email Setup (Resend)

Render's free plan blocks outbound SMTP ports, so this app uses the [Resend](https://resend.com) HTTP API instead — no extra environment variables needed.

**One-time setup:**
1. Sign up free at [resend.com](https://resend.com) — 3,000 emails/month, no credit card
2. **API Keys** → Create Key → copy it
3. **Domains** → Add and verify your sending domain  
   *(or use `onboarding@resend.dev` for testing — only delivers to your own Resend-registered email)*
4. In your admin dashboard → **Email Configuration** → fill in:
   - Resend API Key
   - From Address — e.g. `THREADLINE <orders@yourdomain.com>`
   - Your alert email — where you receive new order notifications
5. Click **Send Test Email** to confirm it works

---

## Admin Routes Reference

| Route | Description |
|---|---|
| `/admin` | Login page |
| `/dashboard` | Main admin panel |
| `/add_design` | Add a new design |
| `/edit_design/<id>` | Edit design details and photos |
| `/delete_design/<id>` | Delete a design |
| `/toggle_stock/<id>` | Toggle in stock / out of stock |
| `/update_status/<id>` | Change order status |
| `/export_orders` | Download all orders as Excel |
| `/sales_analysis` | Sales charts |
| `/change_password` | Change admin password |
| `/send_test_email` | Send a test email |
| `/logout` | Log out |

---

## Security

- Passwords hashed with Werkzeug PBKDF2
- CSRF tokens on all forms (Flask-WTF)
- Admin session timeout after 30 minutes
- File upload validation — type checked, 5 MB max
- Debug mode off by default in production

---
