from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "secret123"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)

# ---------------- DATABASE MODELS ----------------

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_password = db.Column(db.String(100), default="admin123")
    phonepe_name = db.Column(db.String(100), default="Your Name")
    phonepe_number = db.Column(db.String(20), default="9999999999")

class Design(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    design_code = db.Column(db.String(20))
    name = db.Column(db.String(100))
    description = db.Column(db.String(300))
    price = db.Column(db.String(20))
    image = db.Column(db.String(200))
    stock = db.Column(db.String(20), default="In Stock")

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    design = db.Column(db.String(100))
    design_code = db.Column(db.String(20))

    customer_name = db.Column(db.String(100))
    house = db.Column(db.String(100))
    city = db.Column(db.String(100))
    mandal = db.Column(db.String(100))

    email = db.Column(db.String(100))
    size = db.Column(db.String(10))
    quantity = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    payment_image = db.Column(db.String(200))
    status = db.Column(db.String(20), default="Pending")
    completed_at = db.Column(db.String(50), nullable=True)

# --------------- INITIALIZE DATABASE ---------------
with app.app_context():
    db.create_all()
    if not Settings.query.first():
        db.session.add(Settings())
        db.session.commit()

# ---------------- ROUTES ----------------

@app.route('/')
def home():
    designs = Design.query.all()
    return render_template("home.html", designs=designs)

@app.route('/admin', methods=['GET','POST'])
def admin():
    settings = Settings.query.first()
    if request.method == 'POST':
        if request.form['password'] == settings.admin_password:
            session['admin'] = True
            return redirect('/dashboard')
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect('/admin')
    pending_orders   = Order.query.filter_by(status='Pending').all()
    completed_orders = Order.query.filter_by(status='Completed').order_by(Order.id.desc()).all()
    settings = Settings.query.first()
    designs  = Design.query.all()
    return render_template("dashboard.html",
                           pending_orders=pending_orders,
                           completed_orders=completed_orders,
                           settings=settings, designs=designs)

@app.route('/change_password', methods=['GET','POST'])
def change_password():
    if not session.get('admin'):
        return redirect('/admin')

    s = Settings.query.first()
    if request.method == 'POST':
        s.admin_password = request.form['new_password']
        db.session.commit()
        return redirect('/dashboard')

    return render_template("change_password.html")

@app.route('/update_phonepe', methods=['POST'])
def update_phonepe():
    s = Settings.query.first()
    s.phonepe_name = request.form['name']
    s.phonepe_number = request.form['number']
    db.session.commit()
    return redirect('/dashboard')

@app.route('/add_design', methods=['GET','POST'])
def add_design():
    if not session.get('admin'):
        return redirect('/admin')

    if request.method == 'POST':
        code = request.form['code']
        name = request.form['name']
        desc = request.form['description']
        price = request.form['price']
        image = request.files['image']

        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        db.session.add(Design(
            design_code=code,
            name=name,
            description=desc,
            price=price,
            image=filename
        ))
        db.session.commit()
        return redirect('/')

    return render_template("add_design.html")

@app.route('/delete_design/<int:id>')
def delete_design(id):
    if not session.get('admin'):
        return redirect('/admin')
    d = db.session.get(Design, id)
    db.session.delete(d)
    db.session.commit()
    return redirect('/dashboard')

@app.route('/toggle_stock/<int:id>')
def toggle_stock(id):
    if not session.get('admin'):
        return redirect('/admin')
    d = db.session.get(Design, id)
    d.stock = "Out of Stock" if d.stock=="In Stock" else "In Stock"
    db.session.commit()
    return redirect('/dashboard')

@app.route('/order/<design_code>', methods=['GET','POST'])
def order(design_code):
    settings = Settings.query.first()
    design = Design.query.filter_by(design_code=design_code).first()

    if request.method == 'POST':
        payment = request.files['payment']
        filename = secure_filename(payment.filename)
        payment.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_order = Order(
            design=design.name,
            design_code=design.design_code,
            customer_name=request.form['customer_name'],
            house=request.form['house'],
            city=request.form['city'],
            mandal=request.form['mandal'],
            email=request.form['email'],
            size=request.form['size'],
            quantity=request.form['quantity'],
            phone=request.form['phone'],
            payment_image=filename
        )

        db.session.add(new_order)
        db.session.commit()
        order_data = {
            "id": new_order.id,
            "name": new_order.customer_name,
            "phone": new_order.phone,
            "address": f"{new_order.house}, {new_order.city}, {new_order.mandal}",
            "design_name": new_order.design,
            "price": design.price
        }

        invoice_file = create_invoice(order_data)

        return render_template("success.html", invoice=invoice_file)

    return render_template("order.html", design=design, settings=settings)


def create_invoice(order):
    file_name = f"invoice_{order['id']}.pdf"
    file_path = os.path.join("static/invoices", file_name)

    os.makedirs("static/invoices", exist_ok=True)

    c = canvas.Canvas(file_path, pagesize=letter)
    c.setFont("Helvetica", 12)

    c.drawString(200, 750, "T-SHIRT STORE INVOICE")

    c.drawString(50, 700, f"Order ID: {order['id']}")
    c.drawString(50, 680, f"Date: {datetime.now().strftime('%d-%m-%Y')}")

    c.drawString(50, 640, f"Customer Name: {order['name']}")
    c.drawString(50, 620, f"Phone: {order['phone']}")
    c.drawString(50, 600, f"Address: {order['address']}")

    c.drawString(50, 560, f"Product: {order['design_name']}")
    c.drawString(50, 540, f"Amount Paid: ₹{order['price']}")

    c.drawString(50, 500, "Thank you for your order!")

    c.save()

    return file_name


@app.route('/complete_order/<int:id>')
def complete_order(id):
    if not session.get('admin'):
        return redirect('/admin')
    o = db.session.get(Order, id)
    if o:
        o.status = 'Completed'
        o.completed_at = datetime.now().strftime('%d-%m-%Y %I:%M %p')
        db.session.commit()
    return redirect('/dashboard')


@app.route('/sales_analysis')
def sales_analysis():
    if not session.get('admin'):
        return redirect('/admin')

    designs = Design.query.all()
    labels = [d.name for d in designs]
    values = [Order.query.filter_by(design_code=d.design_code).count() for d in designs]

    return render_template("sales_report.html", labels=labels, values=values)


if __name__ == "__main__":
    app.run(debug=True)
