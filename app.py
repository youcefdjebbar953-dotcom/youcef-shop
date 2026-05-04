from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "youcef_shop_secret_2026"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ============================================================
# 🗄️ Models
# ============================================================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(20))
    password = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    is_vip = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    category = db.Column(db.String(50))  # temu, aliexpress, netflix, other
    image = db.Column(db.String(300))
    stock = db.Column(db.Integer, default=1)
    active = db.Column(db.Boolean, default=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_num = db.Column(db.String(20), unique=True)
    user_id = db.Column(db.Integer)
    user_name = db.Column(db.String(100))
    user_phone = db.Column(db.String(20))
    items = db.Column(db.Text)
    total = db.Column(db.Float)
    status = db.Column(db.String(30), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.now)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    product_id = db.Column(db.Integer)
    qty = db.Column(db.Integer, default=1)

# ============================================================
# 🔧 Helpers
# ============================================================
def current_user():
    uid = session.get('user_id')
    if uid:
        return User.query.get(uid)
    return None

def cart_count():
    uid = session.get('user_id')
    if uid:
        return Cart.query.filter_by(user_id=uid).count()
    return 0

@app.context_processor
def inject_globals():
    return dict(user=current_user(), cart_count=cart_count())

STATUS = {
    'pending': 'في الانتظار',
    'confirmed': 'مؤكد',
    'processing': 'قيد المعالجة',
    'shipped': 'تم الشحن',
    'delivered': 'وصل',
    'cancelled': 'ملغي',
}

CATEGORIES = {
    'temu': '🛍️ تيمو',
    'aliexpress': '📦 علي اكسبراس',
    'netflix': '🎬 نتفلكس',
    'other': '✨ خدمات أخرى',
}

# ============================================================
# 🏠 Pages
# ============================================================
@app.route('/')
def index():
    products = Product.query.filter_by(active=True).limit(8).all()
    return render_template('index.html', products=products, categories=CATEGORIES)

@app.route('/shop')
def shop():
    cat = request.args.get('cat', '')
    q = request.args.get('q', '')
    query = Product.query.filter_by(active=True)
    if cat:
        query = query.filter_by(category=cat)
    if q:
        query = query.filter(Product.name.contains(q))
    products = query.all()
    return render_template('shop.html', products=products, categories=CATEGORIES, current_cat=cat, q=q)

@app.route('/product/<int:pid>')
def product(pid):
    p = Product.query.get_or_404(pid)
    return render_template('product.html', product=p)

# ============================================================
# 🛒 Cart
# ============================================================
@app.route('/cart')
def cart():
    uid = session.get('user_id')
    if not uid:
        return redirect(url_for('login'))
    items = Cart.query.filter_by(user_id=uid).all()
    cart_items = []
    total = 0
    for item in items:
        p = Product.query.get(item.product_id)
        if p:
            subtotal = p.price * item.qty
            total += subtotal
            cart_items.append({'cart': item, 'product': p, 'subtotal': subtotal})
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/cart/add/<int:pid>')
def cart_add(pid):
    uid = session.get('user_id')
    if not uid:
        return redirect(url_for('login'))
    existing = Cart.query.filter_by(user_id=uid, product_id=pid).first()
    if existing:
        existing.qty += 1
    else:
        db.session.add(Cart(user_id=uid, product_id=pid, qty=1))
    db.session.commit()
    flash('✅ تمت الإضافة للسلة!', 'success')
    return redirect(request.referrer or url_for('shop'))

@app.route('/cart/remove/<int:cid>')
def cart_remove(cid):
    item = Cart.query.get_or_404(cid)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('cart'))

# ============================================================
# 📦 Orders
# ============================================================
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    uid = session.get('user_id')
    if not uid:
        return redirect(url_for('login'))
    user = User.query.get(uid)
    items = Cart.query.filter_by(user_id=uid).all()
    if not items:
        return redirect(url_for('cart'))

    if request.method == 'POST':
        cart_items = []
        total = 0
        for item in items:
            p = Product.query.get(item.product_id)
            if p:
                subtotal = p.price * item.qty
                total += subtotal
                cart_items.append(f"{p.name} x{item.qty} = {subtotal} دج")

        count = Order.query.count() + 1
        order_num = f"YS{count:04d}"
        order = Order(
            order_num=order_num,
            user_id=uid,
            user_name=request.form.get('name', user.name),
            user_phone=request.form.get('phone', user.phone),
            items='\n'.join(cart_items),
            total=total,
            status='pending',
        )
        db.session.add(order)
        for item in items:
            db.session.delete(item)
        db.session.commit()
        flash(f'🎉 تم تسجيل طلبك رقم {order_num}!', 'success')
        return redirect(url_for('orders'))

    total = sum(Product.query.get(i.product_id).price * i.qty for i in items if Product.query.get(i.product_id))
    return render_template('checkout.html', user=user, total=total)

@app.route('/orders')
def orders():
    uid = session.get('user_id')
    if not uid:
        return redirect(url_for('login'))
    user_orders = Order.query.filter_by(user_id=uid).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=user_orders, STATUS=STATUS)

# ============================================================
# 👤 Auth
# ============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('👋 أهلاً ' + user.name, 'success')
            return redirect(url_for('index'))
        flash('❌ البريد أو كلمة المرور غلط', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('❌ البريد مستخدم مسبقاً', 'error')
            return redirect(url_for('register'))
        user = User(
            name=name, email=email, phone=phone,
            password=generate_password_hash(password),
            is_admin=User.query.count() == 0
        )
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        flash('🎉 تم التسجيل بنجاح!', 'success')
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ============================================================
# 👨‍💼 Admin
# ============================================================
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user or not user.is_admin:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

@app.route('/admin')
@admin_required
def admin():
    total_orders = Order.query.count()
    pending = Order.query.filter_by(status='pending').count()
    revenue = db.session.query(db.func.sum(Order.total)).filter_by(status='delivered').scalar() or 0
    users = User.query.count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    return render_template('admin.html', total_orders=total_orders, pending=pending,
                           revenue=revenue, users=users, recent_orders=recent_orders, STATUS=STATUS)

@app.route('/admin/products', methods=['GET', 'POST'])
@admin_required
def admin_products():
    if request.method == 'POST':
        p = Product(
            name=request.form['name'],
            description=request.form['description'],
            price=float(request.form['price']),
            category=request.form['category'],
            image=request.form.get('image', ''),
            stock=int(request.form.get('stock', 1)),
        )
        db.session.add(p)
        db.session.commit()
        flash('✅ تمت إضافة المنتج!', 'success')
    products = Product.query.all()
    return render_template('admin_products.html', products=products, categories=CATEGORIES)

@app.route('/admin/product/delete/<int:pid>')
@admin_required
def admin_delete_product(pid):
    p = Product.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for('admin_products'))

@app.route('/admin/order/<int:oid>/status', methods=['POST'])
@admin_required
def admin_update_order(oid):
    order = Order.query.get_or_404(oid)
    order.status = request.form['status']
    db.session.commit()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # أضف منتجات تجريبية
        if Product.query.count() == 0:
            samples = [
                Product(name='سماعات بلوتوث من تيمو', description='سماعات لاسلكية عالية الجودة', price=1800, category='temu', image='https://via.placeholder.com/300x300?text=سماعات', stock=10),
                Product(name='ساعة ذكية من علي اكسبراس', description='ساعة ذكية مع شاشة AMOLED', price=4500, category='aliexpress', image='https://via.placeholder.com/300x300?text=ساعة', stock=5),
                Product(name='اشتراك نتفلكس شهر', description='حساب نتفلكس شهر كامل', price=800, category='netflix', image='https://via.placeholder.com/300x300?text=Netflix', stock=99),
                Product(name='اشتراك نتفلكس 3 أشهر', description='حساب نتفلكس 3 أشهر', price=2100, category='netflix', image='https://via.placeholder.com/300x300?text=Netflix3', stock=99),
                Product(name='حقيبة يد من تيمو', description='حقيبة أنيقة بجودة عالية', price=2200, category='temu', image='https://via.placeholder.com/300x300?text=حقيبة', stock=8),
            ]
            db.session.bulk_save_objects(samples)
            db.session.commit()
    app.run(debug=True, host='0.0.0.0', port=5000)
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "خدام 🔥"

if __name__ == "__main__":
    app.run(debug=True)
    