from flask import Flask, request, jsonify, session, render_template
from flask_pymongo import PyMongo
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from bson import ObjectId

# 환경 변수 로드
load_dotenv()

app = Flask(__name__)
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
mongo = PyMongo(app)
db = mongo.db


@app.route("/")
def index():
    return render_template("index.html")

# 회원가입
@app.route("/sign-up")
def sign_up_page():
    return render_template("sign_up.html")
@app.route("/sign-up", methods=["POST"])
def sign_up():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if db.users.find_one({"username": username}):
        return jsonify({"error": "이미 존재하는 사용자입니다."}), 400

    hashed_pw = generate_password_hash(password)
    db.users.insert_one({"username": username, "password": hashed_pw})

    return jsonify({"message": "회원가입 성공!"}), 201

# 로그인
@app.route("/login")
def login_page():
    return render_template("login.html")
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    user = db.users.find_one({"username": username})

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "잘못된 사용자명 또는 비밀번호"}), 401

    session["user_id"] = str(user["_id"])  # MongoDB의 _id는 ObjectId이므로 문자열 변환 필요
    return jsonify({"message": "로그인 성공!"}), 200

# 게시글 작성
@app.route("/create-post")
def create_post_page():
    if "user_id" not in session:
        return render_template("login.html")  # 로그인하지 않은 경우 로그인 페이지로 리다이렉트
    return render_template("create_post.html")
@app.route("/post", methods=["POST"])
def create_post():
    if "user_id" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    data = request.json
    title = data.get("title")
    content = data.get("content")
    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    post = {
        "title": title,
        "content": content,
        "author": user["username"],  # 작성자 정보 추가
        "author_id": session["user_id"],
        "created_at": datetime.utcnow(),
        "likes": 0,
        "liked_users": [],
        "dislikes": 0,
        "disliked_users": []
    }
    result = db.posts.insert_one(post)
    return jsonify({"message": "게시글 작성 완료!", "post_id": str(result.inserted_id)}), 201

# 게시글 목록 조회
@app.route("/posts", methods=["GET"])
def get_posts():
    posts = list(db.posts.find({}, {"_id": 1, "title": 1, "content": 1, "author": 1, "created_at": 1, "likes": 1, "dislikes": 1}))
    for post in posts:
        post["_id"] = str(post["_id"])  # ObjectId -> 문자열 변환
        post["created_at"] = post["created_at"].isoformat()  # ISO 8601 형식으로 변환
    return jsonify(posts)

# 게시글 상세 조회
@app.route("/post/<post_id>", methods=["GET"])
def get_post(post_id):
    post = db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        return jsonify({"error": "게시글을 찾을 수 없습니다."}), 404

    post["_id"] = str(post["_id"])
    post["created_at"] = post["created_at"].isoformat()  # ISO 8601 형식으로 변환
    return jsonify(post)

# 게시글 상세 페이지 렌더링
@app.route("/post/<post_id>/view")
def view_post_page(post_id):
    post = db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        return render_template("404.html"), 404  # 게시글이 없으면 404 페이지로 이동
    return render_template("post_detail.html", post_id=post_id)

# 좋아요 기능
@app.route("/post/<post_id>/like", methods=["POST"])
def like_post(post_id):
    if "user_id" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    post = db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        return jsonify({"error": "게시글을 찾을 수 없습니다."}), 404

    user_id = session["user_id"]

    if user_id in post.get("liked_users", []):
        db.posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"likes": -1}, "$pull": {"liked_users": user_id}}
        )
        return jsonify({"message": "좋아요 취소됨!"}), 200

    if user_id in post.get("disliked_users", []):
        # db.posts.update_one(
        #     {"_id": ObjectId(post_id)},
        #     {"$inc": {"dislikes": -1}, "$pull": {"disliked_users": user_id}}
        # )
        return jsonify({"message": "이미 싫어요를 누름!"}), 200

    # 좋아요 증가 및 유저 목록 업데이트
    db.posts.update_one(
        {"_id": ObjectId(post_id)},
        {"$inc": {"likes": 1}, "$push": {"liked_users": user_id}}
    )
    return jsonify({"message": "좋아요 추가됨!"}), 200

# 싫어요 기능
@app.route("/post/<post_id>/dislike", methods=["POST"])
def dislike_post(post_id):
    if "user_id" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    post = db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        return jsonify({"error": "게시글을 찾을 수 없습니다."}), 404

    user_id = session["user_id"]
    
    if user_id in post.get("disliked_users", []):
        db.posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"dislikes": -1}, "$pull": {"disliked_users": user_id}}
        )
        return jsonify({"message": "싫어요 취소됨!"}), 200
    
    if user_id in post.get("liked_users", []):
        # db.posts.update_one(
        #     {"_id": ObjectId(post_id)},
        #     {"$inc": {"likes": -1}, "$pull": {"liked_users": user_id}}
        # )
        return jsonify({"message": "이미 좋아요를 누름!"}), 200

    # 싫어요 증가 및 유저 목록 업데이트
    db.posts.update_one(
        {"_id": ObjectId(post_id)},
        {"$inc": {"dislikes": 1}, "$push": {"disliked_users": user_id}}
    )
    return jsonify({"message": "싫어요 추가됨!"}), 200

# 게시물 삭제
@app.route("/post/<post_id>", methods=["DELETE"])
def delete_post(post_id):
    if "user_id" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    post = db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        return jsonify({"error": "게시글을 찾을 수 없습니다."}), 404

    # 작성자 확인
    if post["author_id"] != session["user_id"]:
        return jsonify({"error": "게시글을 삭제할 권한이 없습니다."}), 403

    db.posts.delete_one({"_id": ObjectId(post_id)})
    return jsonify({"message": "게시글이 삭제되었습니다."}), 200

# 로그아웃
@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)  # 세션에서 user_id 제거
    return jsonify({"message": "로그아웃 완료!"}), 200

# 로그인 상태 확인
@app.route('/auth/status')
def auth_status():
    logged_in = 'user_id' in session  # 세션에 user_id가 있으면 로그인 상태
    return jsonify({'loggedIn': logged_in})

if __name__ == "__main__":
    app.run(debug=True)