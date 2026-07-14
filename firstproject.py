"""
app.py — Backend for the Instagram-like site.

Connects:
  - The HTML/CSS frontend  (index.html / style.css, served as static files)
  - The PostgreSQL database (instagram_schema.sql)

Setup
-----
1. Create the database and load the schema:
     createdb instagram_clone
     psql instagram_clone < instagram_schema.sql

2. Install dependencies:
     pip install flask psycopg2-binary werkzeug

3. Set your DB connection info as environment variables (or edit the
   DB_CONFIG defaults below):
     export DB_HOST=localhost
     export DB_NAME=instagram_clone
     export DB_USER=postgres
     export DB_PASSWORD=yourpassword
     export DB_PORT=5432

4. Run it:
     python app.py

   Then open http://localhost:5000 in your browser.
"""

import os
from datetime import datetime

import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "dbname": os.environ.get("DB_NAME", "instagram_clone"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "port": os.environ.get("DB_PORT", "5432"),
}


def get_db():
    """Open a new connection with dict-style rows."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


def query(sql, params=None, fetch="all"):
    """Run a query and return rows (or nothing, for INSERT/UPDATE)."""
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            if fetch == "all":
                result = cur.fetchall()
            elif fetch == "one":
                result = cur.fetchone()
            else:
                result = None
            conn.commit()
            return result
    finally:
        conn.close()


def current_user_id():
    return session.get("user_id")


def login_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user_id():
            return jsonify({"error": "Login required"}), 401
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({"error": "username, email, and password are required"}), 400

    existing = query(
        "SELECT id FROM users WHERE username = %s OR email = %s",
        (username, email),
        fetch="one",
    )
    if existing:
        return jsonify({"error": "Username or email already taken"}), 409

    password_hash = generate_password_hash(password)
    user = query(
        """
        INSERT INTO users (username, email, password_hash, full_name)
        VALUES (%s, %s, %s, %s)
        RETURNING id, username, email
        """,
        (username, email, password_hash, data.get("full_name", "")),
        fetch="one",
    )
    session["user_id"] = user["id"]
    return jsonify(user), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    identifier = data.get("username", "").strip()  # username or email
    password = data.get("password", "")

    user = query(
        "SELECT * FROM users WHERE username = %s OR email = %s",
        (identifier, identifier),
        fetch="one",
    )
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = user["id"]
    return jsonify({"id": user["id"], "username": user["username"]})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.route("/api/users/<username>", methods=["GET"])
def get_user(username):
    user = query(
        """
        SELECT id, username, full_name, bio, profile_pic_url, is_private, is_verified,
               (SELECT COUNT(*) FROM posts WHERE user_id = users.id) AS post_count,
               (SELECT COUNT(*) FROM follows WHERE following_id = users.id) AS follower_count,
               (SELECT COUNT(*) FROM follows WHERE follower_id = users.id) AS following_count
        FROM users WHERE username = %s
        """,
        (username,),
        fetch="one",
    )
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)


@app.route("/api/follow/<int:target_id>", methods=["POST"])
@login_required
def follow_user(target_id):
    user_id = current_user_id()
    if user_id == target_id:
        return jsonify({"error": "Cannot follow yourself"}), 400
    query(
        """
        INSERT INTO follows (follower_id, following_id)
        VALUES (%s, %s)
        ON CONFLICT (follower_id, following_id) DO NOTHING
        """,
        (user_id, target_id),
        fetch=None,
    )
    return jsonify({"message": "Followed"})


@app.route("/api/follow/<int:target_id>", methods=["DELETE"])
@login_required
def unfollow_user(target_id):
    query(
        "DELETE FROM follows WHERE follower_id = %s AND following_id = %s",
        (current_user_id(), target_id),
        fetch=None,
    )
    return jsonify({"message": "Unfollowed"})


# ---------------------------------------------------------------------------
# Posts / Feed
# ---------------------------------------------------------------------------

@app.route("/api/posts", methods=["POST"])
@login_required
def create_post():
    data = request.get_json(force=True)
    caption = data.get("caption", "")
    location = data.get("location", "")
    media_urls = data.get("media_urls", [])  # list of {url, type}

    post = query(
        """
        INSERT INTO posts (user_id, caption, location)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (current_user_id(), caption, location),
        fetch="one",
    )

    for i, media in enumerate(media_urls):
        query(
            """
            INSERT INTO post_media (post_id, media_url, media_type, position)
            VALUES (%s, %s, %s, %s)
            """,
            (post["id"], media["url"], media.get("type", "image"), i),
            fetch=None,
        )

    return jsonify({"id": post["id"], "message": "Post created"}), 201


@app.route("/api/feed", methods=["GET"])
@login_required
def feed():
    """Posts from people the current user follows, newest first."""
    rows = query(
        """
        SELECT p.id, p.caption, p.location, p.created_at,
               u.username, u.profile_pic_url,
               (SELECT COUNT(*) FROM likes WHERE post_id = p.id) AS like_count,
               (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comment_count,
               EXISTS(
                   SELECT 1 FROM likes WHERE post_id = p.id AND user_id = %s
               ) AS liked_by_me,
               COALESCE(
                   (SELECT json_agg(json_build_object('url', media_url, 'type', media_type)
                                    ORDER BY position)
                    FROM post_media WHERE post_id = p.id),
                   '[]'
               ) AS media
        FROM posts p
        JOIN users u ON u.id = p.user_id
        WHERE p.user_id = %s
           OR p.user_id IN (SELECT following_id FROM follows WHERE follower_id = %s)
        ORDER BY p.created_at DESC
        LIMIT 50
        """,
        (current_user_id(), current_user_id(), current_user_id()),
    )
    return jsonify(rows)


@app.route("/api/posts/<int:post_id>/like", methods=["POST"])
@login_required
def like_post(post_id):
    query(
        """
        INSERT INTO likes (user_id, post_id) VALUES (%s, %s)
        ON CONFLICT (user_id, post_id) DO NOTHING
        """,
        (current_user_id(), post_id),
        fetch=None,
    )
    return jsonify({"message": "Liked"})


@app.route("/api/posts/<int:post_id>/like", methods=["DELETE"])
@login_required
def unlike_post(post_id):
    query(
        "DELETE FROM likes WHERE user_id = %s AND post_id = %s",
        (current_user_id(), post_id),
        fetch=None,
    )
    return jsonify({"message": "Unliked"})


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@app.route("/api/posts/<int:post_id>/comments", methods=["GET"])
def get_comments(post_id):
    rows = query(
        """
        SELECT c.id, c.content, c.created_at, u.username
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.post_id = %s
        ORDER BY c.created_at ASC
        """,
        (post_id,),
    )
    return jsonify(rows)


@app.route("/api/posts/<int:post_id>/comments", methods=["POST"])
@login_required
def add_comment(post_id):
    data = request.get_json(force=True)
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Comment cannot be empty"}), 400

    comment = query(
        """
        INSERT INTO comments (post_id, user_id, content)
        VALUES (%s, %s, %s)
        RETURNING id, created_at
        """,
        (post_id, current_user_id(), content),
        fetch="one",
    )
    return jsonify(comment), 201


if __name__ == "__main__":
    app.run(debug=True, port=5000)
