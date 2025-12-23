from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pathlib
import uuid
import os
from bson.objectid import ObjectId
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
MONGO_URI = os.getenv("mongodb+srv://jawad:1214@cluster0.ci7lheu.mongodb.net/?appName=Cluster0")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-123")
BASE_DIR = pathlib.Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4", "webm"}
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

# --- DATABASE LOGIC ---
if MONGO_URI:
    client = MongoClient(MONGO_URI)
    db = client["photoapp"]
    users = db["users"]
    media_coll = db["media"]
    comments_coll = db["comments"]
    USING_MONGO = True
else:
    # Dummy storage for local testing without MongoDB
    class InMemoryColl:
        def __init__(self): self._data = []; self._id_counter = 1
        def insert_one(self, doc):
            doc['_id'] = self._id_counter
            self._id_counter += 1
            self._data.append(doc)
            return doc
        def find(self, query=None): return self._data
        def find_one(self, query):
            for item in self._data:
                if all(item.get(k) == v for k, v in query.items()): return item
            return None

    users = InMemoryColl()
    media_coll = InMemoryColl()
    comments_coll = InMemoryColl()
    USING_MONGO = False

# --- HELPERS ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- ROUTES ---

@app.route("/")
def index():
    if 'user_id' in session:
        return redirect(url_for('creator_view'))
    return render_template("login.html")

@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

@app.route("/api/users/register", methods=["POST"])
def register():
    data = request.form if request.form else request.get_json()
    hashed_pw = generate_password_hash(data.get("password"))
    
    user_doc = {
        "name": data.get("name"),
        "email": data.get("email"),
        "password": hashed_pw,
        "role": data.get("role", "consumer"),
        "created_at": datetime.utcnow()
    }
    users.insert_one(user_doc)
    return redirect(url_for("login_page"))

@app.route("/api/users/login", methods=["POST"])
def login():
    data = request.form if request.form else request.get_json()
    user = users.find_one({"email": data.get("email")})

    if user and check_password_hash(user["password"], data.get("password")):
        o =session["user_id"] = str(user["_id"])
        session["user_name"] = user["name"]
        session["role"] = user.get("role", "consumer")
        
        # Dashboard par bhej rahe hain
        return redirect(url_for("creator_view"))
    
    return "Invalid Credentials", 401

@app.route("/consumer")
def consumer_view():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    
    query = request.args.get('q', '').lower()
    all_media = list(media_coll.find())
    
    results = []
    for m in all_media:
        # Search logic
        search_text = f"{m.get('title','')} {m.get('caption','')} {m.get('location','')}".lower()
        if query in search_text:
            m['_id'] = str(m['_id']) # JSON serializable
            results.append(m)
            
    return render_template('consumer.html', media=results, q=query)

@app.route('/creator')
def creator_view():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    
    # Sirf wahi dikhao jo is user ne upload kiya hai
    my_media = [m for m in media_coll.find() if str(m.get('uploader_id')) == session['user_id']]
    for m in my_media: m['_id'] = str(m['_id'])
    
    return render_template('creator.html', uploads=my_media)

@app.route('/creator/upload', methods=['POST'])
def creator_upload():
    if 'user_id' not in session: return redirect(url_for('login_page'))

    file = request.files.get('file')
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        file.save(UPLOAD_DIR / unique_name)

        media_doc = {
            'filename': unique_name,
            'title': request.form.get('title'),
            'caption': request.form.get('caption'),
            'location': request.form.get('location'),
            'people': [p.strip() for p in request.form.get('people', '').split(',') if p.strip()],
            'uploader_name': session.get('user_name'),
            'uploader_id': session.get('user_id'),
            'created_at': datetime.utcnow()
        }
        media_coll.insert_one(media_doc)
        return redirect(url_for('creator_view'))
    
    return "Invalid File", 400

@app.route('/media/<mid>')
def media_view(mid):
    # Flexible ID searching (MongoDB ObjectId vs Plain Integer)
    m = None
    if USING_MONGO:
        try: m = media_coll.find_one({'_id': ObjectId(mid)})
        except: pass
    
    if not m: # Fallback for In-Memory or String IDs
        for item in media_coll.find():
            if str(item.get('_id')) == str(mid):
                m = item; break

    if not m: return "Media Not Found", 404

    # Load Comments
    comments = [c for c in comments_coll.find() if str(c.get('media_id')) == str(mid)]
    return render_template('media.html', media=m, comments=comments)

@app.route('/api/media/<mid>/comment', methods=['POST'])
def add_comment(mid):
    if 'user_id' not in session: return redirect(url_for('login_page'))
    
    comment_doc = {
        'media_id': mid,
        'user_id': session['user_id'],
        'user_name': session['user_name'],
        'text': request.form.get('text'),
        'created_at': datetime.utcnow()
    }
    comments_coll.insert_one(comment_doc)
    return redirect(url_for('media_view', mid=mid))

@app.route('/uploads/<path:filename>')
def serve_file(filename):
    return send_from_directory(str(UPLOAD_DIR), filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True, port=5000)