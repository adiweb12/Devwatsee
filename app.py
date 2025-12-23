import os, random, string, smtplib
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from email.message import EmailMessage
from datetime import timedelta

# ================= APP SETUP =================
app = Flask(__name__)

# ✅ FIXED CORS (MOST IMPORTANT)
CORS(
    app,
    supports_credentials=True,
    resources={r"/*": {"origins": "*"}},
    allow_headers=["Authorization", "Content-Type"]
)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")  # SAME SECRET ✔
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=2)

db = SQLAlchemy(app)
jwt = JWTManager(app)

# ================= EMAIL CONFIG =================
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# ================= DATABASE MODELS =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    category = db.Column(db.String(100))
    section = db.Column(db.String(100))
    video_url = db.Column(db.Text)
    thumbnail_url = db.Column(db.Text)


class SavedVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    video_id = db.Column(db.Integer)


with app.app_context():
    db.create_all()

# ================= EMAIL =================
def send_email(to, new_password):
    msg = EmailMessage()
    msg["Subject"] = "WATSEE - Password Reset"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to
    msg.set_content(
        f"Your new password:\n\n{new_password}\n\nPlease change it after login."
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

# ================= AUTH =================
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json

    if User.query.filter(
        (User.username == data["username"]) |
        (User.email == data["email"])
    ).first():
        return {"success": False, "msg": "User exists"}, 409

    user = User(
        username=data["username"],
        name=data.get("name"),
        email=data["email"],
        password=generate_password_hash(data["password"])
    )

    db.session.add(user)
    db.session.commit()
    return {"success": True}


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(username=data["username"]).first()

    if not user or not check_password_hash(user.password, data["password"]):
        return {"success": False}, 401

    token = create_access_token(identity=user.id)
    return {"success": True, "access_token": token}

# ================= FORGOT PASSWORD =================
@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    email = request.json.get("email")
    user = User.query.filter_by(email=email).first()

    if not user:
        return {"success": False}, 404

    new_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    user.password = generate_password_hash(new_pass)
    db.session.commit()

    send_email(email, new_pass)
    return {"success": True}

# ================= PROFILE =================
@app.route("/profile", methods=["GET"])
@jwt_required()
def profile():
    user = User.query.get(get_jwt_identity())
    return {
        "username": user.username,
        "name": user.name,
        "email": user.email
    }


@app.route("/profile/update", methods=["POST"])
@jwt_required()
def update_profile():
    user = User.query.get(get_jwt_identity())
    data = request.json

    user.name = data.get("name")
    user.email = data.get("email")
    db.session.commit()
    return {"success": True}

# ================= VIDEOS (FIXED) =================
@app.route("/videos", methods=["GET"])
@jwt_required()
def videos():
    vids = Video.query.all()
    return jsonify([
        {
            "id": v.id,
            "title": v.title,
            "category": v.category,
            "section": v.section,
            "video_url": v.video_url,
            "thumbnail": v.thumbnail_url
        } for v in vids
    ])

# ================= SAVE / UNSAVE =================
@app.route("/save", methods=["POST"])
@jwt_required()
def save_video():
    user_id = get_jwt_identity()
    video_id = request.json.get("video_id")

    if SavedVideo.query.filter_by(
        user_id=user_id, video_id=video_id
    ).first():
        return {"saved": True}

    db.session.add(SavedVideo(user_id=user_id, video_id=video_id))
    db.session.commit()
    return {"saved": True}


@app.route("/unsave", methods=["POST"])
@jwt_required()
def unsave_video():
    user_id = get_jwt_identity()
    video_id = request.json.get("video_id")

    SavedVideo.query.filter_by(
        user_id=user_id, video_id=video_id
    ).delete()
    db.session.commit()
    return {"saved": False}

# ================= SAVED LIST =================
@app.route("/saved", methods=["GET"])
@jwt_required()
def saved():
    user_id = get_jwt_identity()

    rows = db.session.query(Video).join(
        SavedVideo, Video.id == SavedVideo.video_id
    ).filter(SavedVideo.user_id == user_id).all()

    return jsonify([
        {
            "id": v.id,
            "title": v.title,
            "thumbnail": v.thumbnail_url
        } for v in rows
    ])

# ================= CHANGE PASSWORD =================
@app.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    user = User.query.get(get_jwt_identity())
    data = request.json

    if not check_password_hash(user.password, data["oldPassword"]):
        return {"success": False}, 401

    user.password = generate_password_hash(data["newPassword"])
    db.session.commit()
    return {"success": True}

# ================= JWT ERROR HANDLER =================
@jwt.unauthorized_loader
def unauthorized(reason):
    return jsonify({"error": "Missing or invalid token"}), 401

# ================= RUN =================
if __name__ == "__main__":
    app.run()
