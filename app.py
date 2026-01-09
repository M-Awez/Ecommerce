from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
import os
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # IMPORTANT: Change this to a strong, random key in production!
# MongoDB Atlas connection
MONGO_URI = os.environ.get("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client['user_db']

# Collections
users_collection = db['users']
mobiles_collection = db['mobiles']
headphones_collection = db['headphones']
laptops_collection = db['laptops']
televisions_collection = db['televisions']
keyboards_collection = db['keyboards']
watches_collection = db['watches']

print("DB connected")

# Home Page
@app.route('/')
def home():
    # If a user is logged in, redirect them to the dashboard
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('dashboard.html') # Or a generic home page if no one is logged in

# Login Page (GET)
@app.route('/login')
def login_form():
    return render_template('login.html')

# Login Submission (POST)
@app.route('/login', methods=['POST'])
def login_post():
    email = request.form['email']
    password = request.form['password']
    user = users_collection.find_one({"email": email})

    if user and check_password_hash(user['password'], password):
        session['user'] = email
        return redirect(url_for('dashboard'))

    return render_template('login.html', message="Invalid email or password.")

# Signup Page (GET)
@app.route('/signup')
def signup_form():
    return render_template('signup.html')

# Signup Submission (POST)
@app.route('/signup', methods=['POST'])
def signup_post():
    email = request.form['email']
    password = request.form['password']
    uname = request.form['uname']
    existing_user = users_collection.find_one({"email": email})

    if existing_user:
        return render_template('signup.html', message="User already exists!")

    hashed_password = generate_password_hash(password)
    users_collection.insert_one({
        "email": email,
        "password": hashed_password,
        "uname": uname,
        "cart": []
    })
    return redirect(url_for('login_form'))

# Dashboard
@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        user = users_collection.find_one({"email": session['user']})
        uname = user.get("uname", "User")
        return render_template('dashboard.html', uname=uname)
    return redirect(url_for('login_form'))

# Logout
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login_form'))

# Add to Cart with category auto-detection
@app.route('/add_to_cart/<item_id>')
def add_to_cart(item_id):
    if 'user' not in session:
        return redirect(url_for('login_form'))

    collections = {
        "mobiles": mobiles_collection,
        "headphones": headphones_collection,
        "laptops": laptops_collection,
        "televisions": televisions_collection,
        "keyboards": keyboards_collection,
        "watches": watches_collection,
    }

    for category, collection in collections.items():
        try:
            item = collection.find_one({"_id": ObjectId(item_id)})
        except:
            # If item_id is not a valid ObjectId for this collection, try the next
            continue

        if item:
            cart_item = {"item_id": item_id, "category": category}
            users_collection.update_one(
                {"email": session['user']},
                {"$addToSet": {"cart": cart_item}}  # Prevent duplicates
            )
            return redirect(url_for('cart'))

    return "Item not found", 404

# View Cart
@app.route('/cart')
def cart():
    if 'user' not in session:
        return redirect(url_for('login_form'))

    user = users_collection.find_one({"email": session['user']})
    cart_entries = user.get('cart', [])

    cart_items = []
    total = 0

    collections = {
        "mobiles": mobiles_collection,
        "headphones": headphones_collection,
        "laptops": laptops_collection,
        "televisions": televisions_collection,
        "keyboards": keyboards_collection,
        "watches": watches_collection,
    }

    for entry in cart_entries:
        category = entry.get('category')
        item_id = entry.get('item_id')

        collection = collections.get(category)
        # FIX applied here: check if collection is None, not if not collection
        if collection is None:
            continue

        try:
            item = collection.find_one({"_id": ObjectId(item_id)})
        except:
            # If item_id is not a valid ObjectId, or other DB error, skip this item
            continue

        if item:
            item['category'] = category
            try:
                item['price'] = int(item.get('price', 0))
            except (ValueError, TypeError):
                item['price'] = 0
            total += item['price']
            item['item_id'] = str(item['_id'])  # For template use
            cart_items.append(item)

    return render_template('cart.html', cart_items=cart_items, total=total)

# Remove from Cart
@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    if 'user' not in session:
        return redirect(url_for('login_form'))

    remove_ids = request.form.getlist('remove_ids')

    user = users_collection.find_one({"email": session['user']})
    current_cart = user.get('cart', [])

    # Filter out entries matching item_ids in remove_ids
    # This correctly removes the dictionary entry from the cart list
    updated_cart = [item for item in current_cart if item['item_id'] not in remove_ids]

    users_collection.update_one(
        {"email": session['user']},
        {"$set": {"cart": updated_cart}}
    )
    return redirect(url_for('cart'))

# Place Order
@app.route('/place_order')
def place_order():
    if 'user' not in session:
        return redirect(url_for('login_form'))

    user = users_collection.find_one({"email": session['user']})
    cart_entries = user.get('cart', [])

    if not cart_entries:
        return render_template('order_result.html', message="Your cart is empty.", ordered_items=[])

    ordered_items = []
    total = 0

    collections = {
        "mobiles": mobiles_collection,
        "headphones": headphones_collection,
        "laptops": laptops_collection,
        "televisions": televisions_collection,
        "keyboards": keyboards_collection,
        "watches": watches_collection,
    }

    for entry in cart_entries:
        category = entry.get('category')
        item_id = entry.get('item_id')

        collection = collections.get(category)
        # FIX applied here: check if collection is None, not if not collection
        if collection is None:
            continue

        try:
            item = collection.find_one({"_id": ObjectId(item_id)})
        except:
            # If item_id is not a valid ObjectId, or other DB error, skip this item
            continue

        if item:
            try:
                price = int(item.get('price', 0))
            except (ValueError, TypeError):
                price = 0
            total += price
            ordered_items.append({
                "name": item.get("name", "Unnamed Item"),
                "price": price,
                "category": category # Include category for better display if needed
            })

    # Clear the cart after placing the order
    users_collection.update_one(
        {"email": session['user']},
        {"$set": {"cart": []}}
    )

    return render_template('order_result.html',
                           message="Order placed successfully!",
                           ordered_items=ordered_items,
                           total=total)

# Product Pages (Assuming these will list items from their respective collections)
@app.route('/mobile')
def mobile():
    if 'user' not in session:
        return redirect(url_for('login_form'))

    user = users_collection.find_one({'email': session['user']})
    uname = user.get('uname')
    mobiles = mobiles_collection.find()
    return render_template('mobile.html', mobiles=mobiles, uname=uname)

@app.route('/headphone')
def headphone():
    if 'user' not in session:
        return redirect(url_for('login_form'))

    user = users_collection.find_one({'email': session['user']})
    uname = user.get('uname')
    headphones = headphones_collection.find()
    return render_template('headphone.html', headphones=headphones, uname=uname)

@app.route('/watch')
def watch():
    if 'user' not in session:
        return redirect(url_for('login_form'))

    user = users_collection.find_one({'email': session['user']})
    uname = user.get('uname')
    watches = watches_collection.find()
    return render_template('watch.html', watches=watches, uname=uname)

@app.route('/television')
def television():
    if 'user' not in session:
        return redirect(url_for('login_form'))

    user = users_collection.find_one({'email': session['user']})
    uname = user.get('uname')
    televisions = televisions_collection.find()
    return render_template('television.html', televisions=televisions, uname=uname)

@app.route('/keyboard')
def keyboard():
    if 'user' not in session:
        return redirect(url_for('login_form'))

    user = users_collection.find_one({'email': session['user']})
    uname = user.get('uname')
    keyboards = keyboards_collection.find()
    return render_template('keyboard.html', keyboards=keyboards, uname=uname)

@app.route('/laptop')
def laptop():
    if 'user' not in session:
        return redirect(url_for('login_form'))

    user = users_collection.find_one({'email': session['user']})
    uname = user.get('uname')
    laptops = laptops_collection.find()
    return render_template('laptop.html', laptops=laptops, uname=uname)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)