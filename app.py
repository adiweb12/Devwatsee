import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from flask_sqlalchemy import SQLAlchemy
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# Enhanced CORS for JWT headers
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

app.config["JWT_SECRET_KEY"] = os.getenv("ADMIN_JWT_SECRET", "dev-secret-123")

# DB Setup
db_url = os.getenv("DATABASE_URL", "sqlite:///test.db") # Fallback to local sqlite
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # Reduced to 100MB for stability

db = SQLAlchemy(app)
jwt = JWTManager(app)

# Cloudinary config
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80))
    email = db.Column(db.String(120))

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    category = db.Column(db.String(100))
    section = db.Column(db.String(100))
    video_url = db.Column(db.Text)
    thumbnail_url = db.Column(db.Text)

with app.app_context():
    db.create_all()

# Admin Login (Make sure these Env Vars are set on Render!)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password123")

@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Missing JSON in request"}), 400
    
    if data.get("username") == ADMIN_USERNAME and data.get("password") == ADMIN_PASSWORD:
        # identity must be a string
        token = create_access_token(identity="admin")
        return jsonify({"success": True, "token": token})

    return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route("/admin/users", methods=["GET"])
@jwt_required()
def admin_users():
    users = User.query.all()
    return jsonify([{"id": u.id, "username": u.username, "email": u.email} for u in users])

@app.route("/admin/videos", methods=["GET"])
@jwt_required()
def admin_videos():
    videos = Video.query.all()
    return jsonify([{
        "id": v.id, "title": v.title, "category": v.category,
        "section": v.section, "video_url": v.video_url, "thumbnail": v.thumbnail_url
    } for v in videos])

@app.route("/admin/videos", methods=["POST"])
@jwt_required()
def add_video():
    try:
        title = request.form.get("title")
        category = request.form.get("category")
        section = request.form.get("section", "Latest")
        video_file = request.files.get("video")
        thumb_file = request.files.get("thumbnail")

        if not all([title, category, video_file, thumb_file]):
            return jsonify({"message": "Missing fields"}), 400

        # Upload to Cloudinary
        v_res = cloudinary.uploader.upload(video_file, resource_type="video", folder="watsee/videos")
        t_res = cloudinary.uploader.upload(thumb_file, folder="watsee/thumbnails")

        new_video = Video(
            title=title, category=category, section=section,
            video_url=v_res["secure_url"], thumbnail_url=t_res["secure_url"]
        )
        db.session.add(new_video)
        db.session.commit()

        return jsonify({"success": True, "message": "Uploaded successfully!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
