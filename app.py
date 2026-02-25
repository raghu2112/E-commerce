from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = 'secret123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)

# ---------------- MODELS -----------------
class Design(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.String(20))
    image = db.Column(db.String(200))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    design = db.Column(db.String(100))
    size = db.Column(db.String(10))
    quantity = db.Column(db.String(10))
    address = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    payment_image = db.Column(db.String(200))
    status = db.Column(db.String(20), default='Pending')

# ---------------- ROUTES -----------------
@app.route('/')
def home():
    designs = Design.query.all()
    return render_template('home.html', designs=designs)

@app.route('/admin', methods=['GET','POST'])
def admin():
    if request.method == 'POST':
        if request.form['password'] == 'admin123':
            session['admin'] = True
            return redirect('/dashboard')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect('/admin')
    orders = Order.query.all()
    return render_template('dashboard.html', orders=orders)

@app.route('/complete/<int:order_id>')
def complete(order_id):
    if not session.get('admin'):
        return redirect('/admin')
    order = Order.query.get(order_id)
    if order:
        order.status = 'Completed'
        db.session.commit()
    return redirect('/dashboard')

@app.route('/add_design', methods=['GET','POST'])
def add_design():
    if not session.get('admin'):
        return redirect('/admin')
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        image = request.files['image']

        if image and image.filename:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            db.session.add(Design(name=name, price=price, image=filename))
            db.session.commit()

        return redirect('/')
    return render_template('add_design.html')

@app.route('/order/<design_name>', methods=['GET','POST'])
def order(design_name):
    if request.method == 'POST':
        size = request.form['size']
        quantity = request.form['quantity']
        address = request.form['address']
        phone = request.form['phone']
        payment = request.files['payment']

        if payment and payment.filename:
            filename = secure_filename(payment.filename)
            payment.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            db.session.add(Order(
                design=design_name,
                size=size,
                quantity=quantity,
                address=address,
                phone=phone,
                payment_image=filename
            ))
            db.session.commit()

        return render_template('success.html')

    return render_template('order.html', design=design_name)

# ---------------- MAIN -----------------
if __name__ == '__main__':
    # create uploads folder if missing
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # create database if missing
    if not os.path.exists('database.db'):
        with app.app_context():
            db.create_all()

    app.run(debug=True)