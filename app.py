from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")
def get_db_connection():
    conn = sqlite3.connect("db/comparison_app.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/compare")
def compare():
    return render_template("compare.html")

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        # いまは保存しない（あとでDBとつなぐ）
        pass
    return render_template("add.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        return "登録完了（仮）"
    return render_template("register.html")

@app.route("/history")
def history():
    return render_template("history.html")

if __name__ == "__main__":
    app.run(debug=True)
