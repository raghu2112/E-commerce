from flask import Flask, render_template, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime, timedelta
from io import BytesIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import smtplib
import os

# ─── Base directory (absolute — works on any platform / Render) ───────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

# ─── CORE ─────────────────────────────────────────────────────────────────────
app.secret_key = os.environ.get('SECRET_KEY', 'CHANGE-THIS-TO-A-LONG-RANDOM-STRING')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
app.config['UPLOAD_FOLDER']           = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['INVOICE_FOLDER']          = os.path.join(BASE_DIR, 'static', 'invoices')
app.config['ALLOWED_EXTENSIONS']      = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['MAX_CONTENT_LENGTH']      = 5 * 1024 * 1024   # 5 MB per file
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

db   = SQLAlchemy(app)
csrf = CSRFProtect(app)


# ══════════════════════════════════════════════════════════════════════════════
#  ORDER STATUS STAGES — must match track_order.html timeline
# ══════════════════════════════════════════════════════════════════════════════
ORDER_STAGES = ['Pending', 'Verifying', 'Processing', 'Shipped', 'Completed']
# 'Cancelled' is a terminal side-branch handled separately


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def allowed_file(filename):
    return (
        isinstance(filename, str) and
        filename.strip() != '' and
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    )


def send_email(to, subject, body):
    """Send email using credentials stored in Settings.
    Uses smtplib directly so credential changes take effect without restart."""
    try:
        s = Settings.query.first()
        if not s or not s.mail_username or not s.mail_password:
            print("[EMAIL] Not configured — skipping.")
            return
        msg = MIMEMultipart()
        msg['From']    = s.mail_username
        msg['To']      = to
        # Encode subject to handle emoji / non-ASCII characters safely
        msg['Subject'] = str(Header(subject, 'utf-8'))
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(s.mail_username, s.mail_password)
            server.sendmail(s.mail_username, [to], msg.as_string())
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")


def send_admin_alert(subject, body):
    """Send alert email to the admin_email address set in Settings."""
    try:
        s = Settings.query.first()
        if s and s.admin_email and s.admin_email.strip():
            send_email(s.admin_email.strip(), subject, body)
    except Exception as e:
        print(f"[ADMIN ALERT ERROR] {e}")


def save_image(file_obj):
    """Validate, sanitise, and save an uploaded image. Returns filename or None."""
    if not file_obj:
        return None
    filename = file_obj.filename
    if not allowed_file(filename):
        return None
    safe_name = secure_filename(filename)
    if not safe_name:
        return None
    file_obj.save(os.path.join(app.config['UPLOAD_FOLDER'], safe_name))
    return safe_name


def safe_int(value, default=1, minimum=None, maximum=None):
    """Convert value to int safely, clamping to min/max if given."""
    try:
        result = int(value)
    except (ValueError, TypeError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  MODELS
# ══════════════════════════════════════════════════════════════════════════════

class Settings(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    admin_password = db.Column(db.String(200), default="")
    phonepe_name   = db.Column(db.String(100), default="Your Name")
    phonepe_number = db.Column(db.String(20),  default="9999999999")
    admin_whatsapp = db.Column(db.String(20),  default="")
    mail_username  = db.Column(db.String(200), default="")
    mail_password  = db.Column(db.String(200), default="")
    admin_email    = db.Column(db.String(200), default="")


class Design(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    design_code    = db.Column(db.String(20), unique=True)
    name           = db.Column(db.String(100))
    description    = db.Column(db.String(300))
    price          = db.Column(db.String(20))
    image          = db.Column(db.String(200))
    stock          = db.Column(db.String(20), default="In Stock")
    stock_quantity = db.Column(db.Integer,    default=10)
    images         = db.relationship(
        'DesignImage', backref='design',
        cascade='all, delete-orphan',
        order_by='DesignImage.sort_order'
    )


class DesignImage(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    design_id  = db.Column(db.Integer, db.ForeignKey('design.id'), nullable=False)
    filename   = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, default=0)


class Order(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    design            = db.Column(db.String(100))
    design_code       = db.Column(db.String(20))
    customer_name     = db.Column(db.String(100))
    house             = db.Column(db.String(100))
    city              = db.Column(db.String(100))
    mandal            = db.Column(db.String(100))
    pincode           = db.Column(db.String(10),  default="")
    email             = db.Column(db.String(100))
    size              = db.Column(db.String(10))
    quantity          = db.Column(db.String(10))
    phone             = db.Column(db.String(20))
    payment_image     = db.Column(db.String(200))
    status            = db.Column(db.String(20),  default="Pending")
    created_at        = db.Column(db.String(50),  nullable=True)
    completed_at      = db.Column(db.String(50),  nullable=True)
    cancelled_at      = db.Column(db.String(50),  nullable=True)
    status_updated_at = db.Column(db.String(50),  nullable=True)


# ── Startup: create tables, folders, seed settings, auto-migrate images ────────
with app.app_context():
    db.create_all()

    if not Settings.query.first():
        db.session.add(Settings(admin_password=generate_password_hash("Raghu@123")))
        db.session.commit()

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['INVOICE_FOLDER'], exist_ok=True)

    # Auto-migrate: seed DesignImage from existing Design.image (idempotent)
    for d in Design.query.all():
        if d.image and not DesignImage.query.filter_by(design_id=d.id, sort_order=0).first():
            db.session.add(DesignImage(design_id=d.id, filename=d.image, sort_order=0))
    db.session.commit()


# ══════════════════════════════════════════════════════════════════════════════
#  ERROR HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(413)
def file_too_large(e):
    return render_template("404.html", size_error=True), 413

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template("404.html", server_error=True), 500


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    designs  = Design.query.all()
    settings = Settings.query.first()
    return render_template("home.html", designs=designs, settings=settings)


@app.route('/track', methods=['GET', 'POST'])
def track_order():
    orders = []; searched = False; phone = ''
    if request.method == 'POST':
        phone    = request.form.get('phone', '').strip()
        searched = True
        if phone:
            orders = Order.query.filter_by(phone=phone).order_by(Order.id.desc()).all()
    return render_template("track_order.html", orders=orders, searched=searched, phone=phone)


@app.route('/order/<design_code>', methods=['GET', 'POST'])
def order(design_code):
    settings = Settings.query.first()
    design   = Design.query.filter_by(design_code=design_code).first()

    if not design or design.stock == "Out of Stock":
        return redirect('/')

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()

        # Prevent duplicate pending orders for the same design + phone
        duplicate = Order.query.filter_by(
            phone=phone, design_code=design_code, status='Pending'
        ).first()
        if duplicate:
            return render_template("order.html", design=design, settings=settings,
                                   duplicate=True, file_error=None)

        # Validate payment screenshot
        payment = request.files.get('payment')
        if not payment or not allowed_file(payment.filename):
            return render_template("order.html", design=design, settings=settings,
                                   duplicate=False,
                                   file_error="Only PNG / JPG / JPEG / GIF / WEBP images are allowed.")

        qty = safe_int(request.form.get('quantity', 1), default=1, minimum=1)

        filename = secure_filename(payment.filename)
        payment.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_order = Order(
            design        = design.name,
            design_code   = design.design_code,
            customer_name = request.form.get('customer_name', '').strip(),
            house         = request.form.get('house', '').strip(),
            city          = request.form.get('city', '').strip(),
            mandal        = request.form.get('mandal', '').strip(),
            pincode       = request.form.get('pincode', '').strip(),
            email         = request.form.get('email', '').strip(),
            size          = request.form.get('size', 'M'),
            quantity      = str(qty),
            phone         = phone,
            payment_image = filename,
            created_at    = datetime.now().strftime('%d-%m-%Y %I:%M %p'),
        )
        db.session.add(new_order)

        # Decrement stock
        design.stock_quantity = max(0, design.stock_quantity - qty)
        if design.stock_quantity == 0:
            design.stock = "Out of Stock"

        db.session.commit()

        invoice_fname = create_invoice({
            "id":          new_order.id,
            "name":        new_order.customer_name,
            "phone":       new_order.phone,
            "address":     f"{new_order.house}, {new_order.city}, {new_order.mandal} - {new_order.pincode}",
            "design_name": new_order.design,
            "price":       design.price,
            "size":        new_order.size,
            "quantity":    new_order.quantity,
        })

        # Customer confirmation email
        send_email(
            new_order.email,
            f"Order Confirmed #{new_order.id} | THREADLINE",
            f"""Hi {new_order.customer_name},

Your order has been placed successfully!

Order ID   : #{new_order.id}
Design     : {new_order.design}
Size       : {new_order.size}  |  Qty: {new_order.quantity}
Amount     : Rs.{design.price}
Placed At  : {new_order.created_at}

Delivery Address:
{new_order.house}, {new_order.city}, {new_order.mandal} - {new_order.pincode}

Estimated Delivery: 3-5 business days after payment verification.
Track your order at: /track

Thank you — THREADLINE Team
"""
        )

        # Admin new-order alert
        send_admin_alert(
            f"New Order #{new_order.id} — {new_order.customer_name}",
            f"""New order received on THREADLINE!

Order #{new_order.id}
Customer : {new_order.customer_name}
Phone    : {new_order.phone}
Email    : {new_order.email}
Design   : {new_order.design} ({new_order.size}) x{new_order.quantity}
Amount   : Rs.{design.price}
Address  : {new_order.house}, {new_order.city}, {new_order.mandal} - {new_order.pincode}
Time     : {new_order.created_at}

Go to dashboard to update the order status.
"""
        )

        return render_template("success.html", invoice=invoice_fname)

    return render_template("order.html", design=design, settings=settings,
                           duplicate=False, file_error=None)


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN AUTH
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    settings = Settings.query.first()
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if settings and check_password_hash(settings.admin_password, password):
            session.permanent = True
            session['admin']  = True
            return redirect('/dashboard')
        error = "Incorrect password. Please try again."
    return render_template("login.html", error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if not session.get('admin'):
        return redirect('/admin')
    s = Settings.query.first()
    if request.method == 'POST':
        new_pw = request.form.get('new_password', '').strip()
        if new_pw:
            s.admin_password = generate_password_hash(new_pw)
            db.session.commit()
        return redirect('/dashboard')
    return render_template("change_password.html")


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect('/admin')

    active_orders    = Order.query.filter(
        Order.status.notin_(['Completed', 'Cancelled'])
    ).order_by(Order.id.desc()).all()
    completed_orders = Order.query.filter_by(status='Completed').order_by(Order.id.desc()).all()
    cancelled_orders = Order.query.filter_by(status='Cancelled').order_by(Order.id.desc()).all()
    designs          = Design.query.all()
    settings         = Settings.query.first()

    total_revenue = 0
    monthly_revenue = 0
    current_month = datetime.now().strftime('%m-%Y')
    for o in completed_orders:
        d = Design.query.filter_by(design_code=o.design_code).first()
        if d:
            try:
                amt = float(d.price) * safe_int(o.quantity, default=1, minimum=0)
                total_revenue += amt
                if o.completed_at and current_month in o.completed_at:
                    monthly_revenue += amt
            except Exception:
                pass

    best_design = "N/A"
    best_count  = 0
    for d in designs:
        cnt = Order.query.filter_by(design_code=d.design_code).count()
        if cnt > best_count:
            best_count  = cnt
            best_design = d.name

    return render_template("dashboard.html",
        active_orders=active_orders,
        completed_orders=completed_orders,
        cancelled_orders=cancelled_orders,
        designs=designs,
        settings=settings,
        total_revenue=int(total_revenue),
        monthly_revenue=int(monthly_revenue),
        best_design=best_design,
        order_stages=ORDER_STAGES,
    )


# ── UPDATE ORDER STATUS (dropdown) ───────────────────────────────────────────
@app.route('/update_status/<int:order_id>', methods=['POST'])
def update_status(order_id):
    if not session.get('admin'):
        return redirect('/admin')

    o = db.session.get(Order, order_id)
    if not o:
        return redirect('/dashboard')

    new_status = request.form.get('status', '').strip()
    if new_status not in ORDER_STAGES + ['Cancelled']:
        return redirect('/dashboard')

    old_status = o.status
    now        = datetime.now().strftime('%d-%m-%Y %I:%M %p')

    if new_status == 'Completed':
        o.completed_at = now
        # If reverting from a forward state, keep completed_at set
    elif new_status == 'Cancelled':
        o.cancelled_at = now
        # Restore stock
        d = Design.query.filter_by(design_code=o.design_code).first()
        if d:
            try:
                d.stock_quantity += safe_int(o.quantity, default=1, minimum=0)
                d.stock = "In Stock"
            except Exception:
                pass
    else:
        # Non-terminal stage — clear any stale terminal timestamps from prior mistakes
        o.status_updated_at = now
        o.completed_at  = None   # Clear if admin reverts from Completed
        o.cancelled_at  = None   # Clear if admin reverts from Cancelled (also restores stock above)

    o.status = new_status
    db.session.commit()

    # Send status-change email to customer (only on actual status change)
    if new_status != old_status:
        email_map = {
            'Verifying':  (
                "Payment Verification — THREADLINE",
                f"Hi {o.customer_name},\n\nWe have received your payment screenshot and are currently verifying it.\n\n"
                f"Order #{o.id} — {o.design} ({o.size} x{o.quantity})\n\n"
                f"We will update you once verification is complete.\n\nThank you — THREADLINE Team"
            ),
            'Processing': (
                "Order Being Processed — THREADLINE",
                f"Hi {o.customer_name},\n\nGreat news! Payment verified. Your order is now being printed and prepared.\n\n"
                f"Order #{o.id} — {o.design} ({o.size} x{o.quantity})\n\n"
                f"We will notify you once it is shipped.\n\nThank you — THREADLINE Team"
            ),
            'Shipped':    (
                "Your Order Is On Its Way — THREADLINE",
                f"Hi {o.customer_name},\n\nYour order has been shipped!\n\n"
                f"Order #{o.id} — {o.design} ({o.size} x{o.quantity})\n\n"
                f"Estimated delivery: 3-5 business days.\nTrack your order: /track\n\nThank you — THREADLINE Team"
            ),
            'Completed':  (
                "Order Delivered — THREADLINE",
                f"Hi {o.customer_name},\n\nYour order has been marked as delivered. We hope you love it!\n\n"
                f"Order #{o.id} — {o.design} ({o.size} x{o.quantity})\n\n"
                f"Thank you for shopping with THREADLINE!"
            ),
            'Cancelled':  (
                "Order Cancelled — THREADLINE",
                f"Hi {o.customer_name},\n\nYour order #{o.id} ({o.design}) has been cancelled.\n"
                f"If this was a mistake, please contact us.\n\nThank you — THREADLINE Team"
            ),
        }
        if new_status in email_map:
            subject, body = email_map[new_status]
            send_email(o.email, subject, body)

    return redirect('/dashboard')


# ── SETTINGS ──────────────────────────────────────────────────────────────────
@app.route('/update_phonepe', methods=['POST'])
def update_phonepe():
    if not session.get('admin'):
        return redirect('/admin')
    s = Settings.query.first()
    s.phonepe_name   = request.form.get('name', '').strip()
    s.phonepe_number = request.form.get('number', '').strip()
    s.admin_whatsapp = request.form.get('whatsapp', '').strip().replace('+', '').replace(' ', '')
    db.session.commit()
    return redirect('/dashboard')


@app.route('/update_email_config', methods=['POST'])
def update_email_config():
    if not session.get('admin'):
        return redirect('/admin')
    s = Settings.query.first()
    s.mail_username = request.form.get('mail_username', '').strip()
    # Only update password if a new one was entered (blank = keep existing)
    new_pw = request.form.get('mail_password', '').strip()
    if new_pw:
        s.mail_password = new_pw
    s.admin_email   = request.form.get('admin_email', '').strip()
    db.session.commit()
    return redirect('/dashboard')


# ── DESIGN MANAGEMENT ─────────────────────────────────────────────────────────
@app.route('/add_design', methods=['GET', 'POST'])
def add_design():
    if not session.get('admin'):
        return redirect('/admin')
    error = None
    if request.method == 'POST':
        images       = request.files.getlist('images')
        valid_images = [f for f in images if f and allowed_file(f.filename)]

        if not valid_images:
            error = "Please upload at least one image (PNG, JPG, JPEG, GIF, WEBP)."
        else:
            qty            = safe_int(request.form.get('stock_quantity', 10), default=10, minimum=0)
            first_filename = save_image(valid_images[0])
            if not first_filename:
                error = "Failed to save the first image. Please try again."
            else:
                new_design = Design(
                    design_code    = request.form.get('code', '').strip(),
                    name           = request.form.get('name', '').strip(),
                    description    = request.form.get('description', '').strip(),
                    price          = request.form.get('price', '0').strip(),
                    image          = first_filename,
                    stock          = "In Stock" if qty > 0 else "Out of Stock",
                    stock_quantity = qty,
                )
                db.session.add(new_design)
                db.session.flush()  # get new_design.id before commit

                # Save all images as DesignImage records
                for i, img_file in enumerate(valid_images):
                    fname = first_filename if i == 0 else save_image(img_file)
                    if fname:
                        db.session.add(DesignImage(
                            design_id  = new_design.id,
                            filename   = fname,
                            sort_order = i,
                        ))
                db.session.commit()
                return redirect('/dashboard')

    return render_template("add_design.html", error=error)


@app.route('/edit_design/<int:design_id>', methods=['GET', 'POST'])
def edit_design(design_id):
    if not session.get('admin'):
        return redirect('/admin')
    d = db.session.get(Design, design_id)
    if not d:
        return redirect('/dashboard')
    error = None

    if request.method == 'POST':
        d.name           = request.form.get('name', d.name).strip()
        d.description    = request.form.get('description', d.description).strip()
        d.price          = request.form.get('price', d.price).strip()
        d.stock_quantity = safe_int(request.form.get('stock_quantity', d.stock_quantity),
                                    default=d.stock_quantity, minimum=0)
        d.stock          = "In Stock" if d.stock_quantity > 0 else "Out of Stock"

        new_images = request.files.getlist('images')
        valid_new  = [f for f in new_images if f and allowed_file(f.filename)]
        if valid_new:
            max_order = db.session.query(db.func.max(DesignImage.sort_order))\
                          .filter_by(design_id=d.id).scalar()
            max_order = max_order if max_order is not None else -1
            for i, img_file in enumerate(valid_new):
                fname = save_image(img_file)
                if fname:
                    db.session.add(DesignImage(
                        design_id  = d.id,
                        filename   = fname,
                        sort_order = max_order + 1 + i,
                    ))

        # Keep Design.image in sync with first DesignImage
        first = DesignImage.query.filter_by(design_id=d.id)\
                  .order_by(DesignImage.sort_order).first()
        if first:
            d.image = first.filename

        db.session.commit()
        return redirect('/dashboard')

    return render_template("edit_design.html", design=d, error=error)


@app.route('/delete_design_image/<int:image_id>')
def delete_design_image(image_id):
    if not session.get('admin'):
        return redirect('/admin')
    img = db.session.get(DesignImage, image_id)
    if not img:
        return redirect('/dashboard')

    design_id = img.design_id
    count = DesignImage.query.filter_by(design_id=design_id).count()
    if count > 1:
        db.session.delete(img)
        # Update primary image reference
        new_first = DesignImage.query.filter_by(design_id=design_id)\
                      .order_by(DesignImage.sort_order).first()
        if new_first:
            design = db.session.get(Design, design_id)
            if design:
                design.image = new_first.filename
        db.session.commit()

    return redirect(f'/edit_design/{design_id}')


@app.route('/delete_design/<int:design_id>')
def delete_design(design_id):
    if not session.get('admin'):
        return redirect('/admin')
    d = db.session.get(Design, design_id)
    if d:
        db.session.delete(d)
        db.session.commit()
    return redirect('/dashboard')


@app.route('/toggle_stock/<int:design_id>')
def toggle_stock(design_id):
    if not session.get('admin'):
        return redirect('/admin')
    d = db.session.get(Design, design_id)
    if d:
        d.stock = "Out of Stock" if d.stock == "In Stock" else "In Stock"
        db.session.commit()
    return redirect('/dashboard')


# ── EXPORT ────────────────────────────────────────────────────────────────────
@app.route('/export_orders')
def export_orders():
    if not session.get('admin'):
        return redirect('/admin')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders"
    headers = ['ID', 'Design', 'Code', 'Customer', 'House', 'City', 'Mandal',
               'Pincode', 'Phone', 'Email', 'Size', 'Qty', 'Status',
               'Created At', 'Completed At', 'Cancelled At']
    ws.append(headers)
    for cell in ws[1]:
        cell.font      = Font(bold=True, color="FFFFFF")
        cell.fill      = PatternFill("solid", fgColor="FF6B00")
        cell.alignment = Alignment(horizontal="center")
    for o in Order.query.order_by(Order.id.desc()).all():
        ws.append([
            o.id, o.design, o.design_code, o.customer_name,
            o.house or '', o.city or '', o.mandal or '',
            o.pincode or '', o.phone or '', o.email or '',
            o.size or '', o.quantity or '', o.status or '',
            o.created_at or '', o.completed_at or '', o.cancelled_at or '',
        ])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(
            max(len(str(c.value or '')) for c in col) + 4, 40)
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    fname = f"orders_{datetime.now().strftime('%d%m%Y_%H%M')}.xlsx"
    return send_file(
        output, download_name=fname, as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/sales_analysis')
def sales_analysis():
    if not session.get('admin'):
        return redirect('/admin')
    designs = Design.query.all()
    return render_template("sales_report.html",
        labels=[d.name for d in designs],
        values=[Order.query.filter_by(design_code=d.design_code).count() for d in designs],
    )


# ══════════════════════════════════════════════════════════════════════════════
#  INVOICE GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def create_invoice(o):
    fname     = f"invoice_{o['id']}.pdf"
    full_path = os.path.join(app.config['INVOICE_FOLDER'], fname)
    c = canvas.Canvas(full_path, pagesize=letter)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(180, 760, "THREADLINE — INVOICE")

    c.setFont("Helvetica", 12)
    lines = [
        (720, f"Order ID  : #{o['id']}"),
        (700, f"Date      : {datetime.now().strftime('%d-%m-%Y')}"),
        (670, f"Customer  : {o['name']}"),
        (650, f"Phone     : {o['phone']}"),
        (630, f"Address   : {o['address']}"),
        (600, f"Product   : {o['design_name']}"),
        (580, f"Size      : {o.get('size', '')}"),
        (560, f"Quantity  : {o.get('quantity', '')}"),
        (540, f"Amount    : Rs.{o['price']}"),
        (518, "Estimated Delivery: 3-5 business days"),
    ]
    for y, text in lines:
        c.drawString(50, y, text)

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 490, "Thank you for shopping with THREADLINE!")
    c.save()
    return fname


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Never run with debug=True in production.
    # Set FLASK_DEBUG=1 locally only.
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode)
