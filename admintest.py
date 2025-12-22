import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from flask_sqlalchemy import SQLAlchemy
import cloudinary
import cloudinary.uploader

# ================= APP SETUP =================
app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = os.getenv("ADMIN_JWT_SECRET")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
jwt = JWTManager(app)

# ================= CLOUDINARY =================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# ================= DATABASE MODELS =================
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

# ================= ADMIN CREDENTIALS =================
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# ================= ADMIN LOGIN =================
@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.json

    if (
        data.get("username") == ADMIN_USERNAME and
        data.get("password") == ADMIN_PASSWORD
    ):
        token = create_access_token(identity="admin")
        return {"success": True, "token": token}

    return {"success": False}, 401

# ================= VIEW USERS =================
@app.route("/admin/users", methods=["GET"])
@jwt_required()
def admin_users():
    if get_jwt_identity() != "admin":
        return {"error": "Forbidden"}, 403

    users = User.query.all()
    return jsonify([
        {"id": u.id, "username": u.username, "email": u.email}
        for u in users
    ])

# ================= VIEW VIDEOS =================
@app.route("/admin/videos", methods=["GET"])
@jwt_required()
def admin_videos():
    if get_jwt_identity() != "admin":
        return {"error": "Forbidden"}, 403

    videos = Video.query.all()
    return jsonify([
        {
            "id": v.id,
            "title": v.title,
            "category": v.category,
            "section": v.section,
            "video_url": v.video_url,
            "thumbnail": v.thumbnail_url
        } for v in videos
    ])

# ================= ADD VIDEO =================
@app.route("/admin/videos", methods=["POST"])
@jwt_required()
def add_video():
    if get_jwt_identity() != "admin":
        return {"error": "Forbidden"}, 403

    title = request.form.get("title")
    category = request.form.get("category")
    section = request.form.get("section")

    video = request.files.get("video")
    thumbnail = request.files.get("thumbnail")

    if not all([title, category, video, thumbnail]):
        return {"success": False, "message": "Missing fields"}, 400

    # Upload to Cloudinary
    video_res = cloudinary.uploader.upload(
        video,
        resource_type="video",
        folder="watsee/videos"
    )

    thumb_res = cloudinary.uploader.upload(
        thumbnail,
        folder="watsee/thumbnails"
    )

    v = Video(
        title=title,
        category=category,
        section=section,
        video_url=video_res["secure_url"],
        thumbnail_url=thumb_res["secure_url"]
    )

    db.session.add(v)
    db.session.commit()

    return {"success": True}

# ================= UPDATE VIDEO =================
@app.route("/admin/videos/<int:video_id>", methods=["PUT"])
@jwt_required()
def update_video(video_id):
    if get_jwt_identity() != "admin":
        return {"error": "Forbidden"}, 403

    data = request.json
    video = Video.query.get(video_id)

    if not video:
        return {"error": "Not found"}, 404

    video.title = data.get("title", video.title)
    video.category = data.get("category", video.category)
    video.section = data.get("section", video.section)

    db.session.commit()
    return {"success": True}

# ================= RUN =================
if __name__ == "__main__":
    app.run()