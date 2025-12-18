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
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = get_db_connection()

    # 商品一覧（プルダウン用）
    products = conn.execute(
        "SELECT id, name FROM items ORDER BY name"
    ).fetchall()

    product_id = request.args.get("product_id")
    prices = None
    cheapest = None
    max_diff = 0

    if product_id:
        rows = conn.execute(
            """
            SELECT
                s.name AS store_name,
                p.price
            FROM prices p
            JOIN stores s ON p.store_id = s.id
            WHERE p.item_id = ?
            ORDER BY p.price
            """,
            (product_id,)
        ).fetchall()

        if rows:
            min_price = rows[0]["price"]
            prices = []

            for r in rows:
                diff = r["price"] - min_price
                prices.append({
                    "store_name": r["store_name"],
                    "price": r["price"],
                    "diff": diff,
                    "is_cheapest": diff == 0
                })

            cheapest = prices[0]
            max_diff = prices[-1]["price"] - min_price

    conn.close()

    return render_template(
        "compare.html",
        products=products,
        prices=prices,
        selected_product_id=int(product_id) if product_id else None,
        cheapest=cheapest,
        max_diff=max_diff
    )


@app.route("/add", methods=["GET", "POST"])
def add():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        item_name = request.form["item_name"]
        shop_name = request.form["shop_name"]
        price = int(request.form["price"])
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()

        # --- 商品 ---
        item = conn.execute(
            "SELECT id FROM items WHERE name = ?",
            (item_name,)
        ).fetchone()

        if item:
            item_id = item["id"]
        else:
            cur = conn.execute(
                "INSERT INTO items (name) VALUES (?)",
                (item_name,)
            )
            item_id = cur.lastrowid

        # --- 店舗 ---
        store = conn.execute(
            "SELECT id FROM stores WHERE name = ?",
            (shop_name,)
        ).fetchone()

        if store:
            store_id = store["id"]
        else:
            cur = conn.execute(
                "INSERT INTO stores (name) VALUES (?)",
                (shop_name,)
            )
            store_id = cur.lastrowid

        # --- 価格 ---
        conn.execute(
            """
            INSERT INTO prices (item_id, store_id, price, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (item_id, store_id, price, created_at)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("history"))

    return render_template("add.html")


@app.route("/history")
def history():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT
            i.name AS item_name,
            s.name AS shop_name,
            p.price,
            p.created_at
        FROM prices p
        JOIN items i ON p.item_id = i.id
        JOIN stores s ON p.store_id = s.id
        ORDER BY p.created_at DESC
        """
    ).fetchall()

    conn.close()

    return render_template("history.html", rows=rows)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
