from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "dummy-secret-key"


# --------------------
# DB接続
# --------------------
def get_db_connection():
    conn = sqlite3.connect("db/comparison_app.db")
    conn.row_factory = sqlite3.Row
    return conn


# --------------------
# TOP
# --------------------
@app.route("/")
def index():
    return render_template("index.html")


# --------------------
# 会員登録
# --------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["nickname"]
        email = request.form["email"]
        password = request.form["password"]

        password_hash = generate_password_hash(password)
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO users (username, password_hash, created_at, email)
            VALUES (?, ?, ?, ?)
            """,
            (username, email, password_hash, created_at)
        )
        conn.commit()
        conn.close()

        # 登録と同時にログイン状態にする
        session["logged_in"] = True
        session["username"] = username

        return redirect(url_for("dashboard"))

    return render_template("register.html")


# --------------------
# ログイン
# --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["logged_in"] = True
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))

        return "ログイン失敗"

    return render_template("login.html")


# --------------------
# ダッシュボード
# --------------------
@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        nickname=session.get("username")
    )


# --------------------
# その他
# --------------------
@app.route("/compare")
def compare():
    return render_template("compare.html")

@app.route("/add", methods=["GET", "POST"])
def add():
    return render_template("add.html")

@app.route("/history")
def history():
    return render_template("history.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
