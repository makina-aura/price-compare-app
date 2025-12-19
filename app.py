from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta

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
            (username, password_hash, created_at, email)
        )
        conn.commit()
        conn.close()

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
# 価格比較
# --------------------
@app.route("/compare")
def compare():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = get_db_connection()

    # 日付計算
    today = date.today()
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    month_end = next_month - timedelta(days=1)

    today_start = today.strftime("%Y-%m-%d 00:00:00")
    today_end = today.strftime("%Y-%m-%d 23:59:59")

    # 今日登録された商品のみ
    products = conn.execute(
        """
        SELECT DISTINCT i.id, i.name
        FROM items i
        JOIN prices p ON p.item_id = i.id
        WHERE p.created_at BETWEEN ? AND ?
        ORDER BY i.name
        """,
        (today_start, today_end)
    ).fetchall()

    product_id = request.args.get("product_id")

    prices = None
    cheapest = None
    max_diff = 0

    # --------------------
    # 商品選択時
    # --------------------
    if product_id:
        rows = conn.execute(
            """
            SELECT
                p.id AS price_id,
                s.name AS store_name,
                p.price,
                CASE WHEN EXISTS (
                    SELECT 1 FROM favorites f WHERE f.price_id = p.id
                ) THEN 1 ELSE 0 END AS is_favorite
            FROM prices p
            JOIN stores s ON p.store_id = s.id
            WHERE p.item_id = ?
            """,
            (product_id,)
        ).fetchall()

        if rows:
            max_price = max(r["price"] for r in rows)

            prices = []
            favorite_price = None
            favorite_store = None

            for r in rows:
                if r["is_favorite"]:
                    favorite_price = r["price"]
                    favorite_store = r["store_name"]

                prices.append({
                    "price_id": r["price_id"],
                    "store_name": r["store_name"],
                    "price": r["price"],
                    "diff": max_price - r["price"],
                    "is_favorite": bool(r["is_favorite"])
                })

            if favorite_price is not None:
                max_diff = max_price - favorite_price
                cheapest = {"store_name": favorite_store}
            else:
                max_diff = 0
                cheapest = None

    # --------------------
    # 月間累計
    # --------------------
    total_saved_month = conn.execute(
        """
        WITH fav AS (
          SELECT
            p.item_id,
            p.price AS fav_price
          FROM favorites f
          JOIN prices p ON p.id = f.price_id
          WHERE f.created_at BETWEEN ? AND ?
        ),
        maxp AS (
          SELECT
            item_id,
            MAX(price) AS max_price
          FROM prices
          GROUP BY item_id
        )
        SELECT COALESCE(SUM(maxp.max_price - fav.fav_price), 0) AS total
        FROM fav
        JOIN maxp ON fav.item_id = maxp.item_id
        """,
        (
            month_start.strftime("%Y-%m-%d 00:00:00"),
            month_end.strftime("%Y-%m-%d 23:59:59"),
        )
    ).fetchone()["total"]

    conn.close()

    return render_template(
        "compare.html",
        today=today.strftime("%Y/%m/%d"),
        products=products,
        prices=prices,
        selected_product_id=int(product_id) if product_id else None,
        cheapest=cheapest,
        max_diff=max_diff,
        total_saved=total_saved_month
    )


# --------------------
# ★選択（1商品1つ）
# --------------------
@app.route("/favorite/<int:price_id>")
def favorite(price_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = get_db_connection()

    item_id = conn.execute(
        "SELECT item_id FROM prices WHERE id = ?",
        (price_id,)
    ).fetchone()["item_id"]

    conn.execute(
        """
        DELETE FROM favorites
        WHERE price_id IN (
            SELECT id FROM prices WHERE item_id = ?
        )
        """,
        (item_id,)
    )

    conn.execute(
        "INSERT INTO favorites (price_id, created_at) VALUES (?, ?)",
        (price_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )

    conn.commit()
    conn.close()

    return redirect(request.referrer or url_for("compare"))


# --------------------
# 商品登録
# --------------------
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


# --------------------
# 履歴
# --------------------
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


# --------------------
# ログアウト
# --------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
