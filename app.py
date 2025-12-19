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

        # ★ここ：VALUES の順番をSQL列順に合わせる（元コードは順番ズレでバグります）
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

    return render_template("dashboard.html", nickname=session.get("username"))


# --------------------
# 価格比較
# --------------------
@app.route("/compare")
def compare():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = get_db_connection()

    # --------------------
    # 日付計算
    # --------------------
    today = date.today()
    month_start_date = today.replace(day=1)
    next_month = (month_start_date + timedelta(days=32)).replace(day=1)
    month_end_date = next_month - timedelta(days=1)

    month_start = month_start_date.strftime("%Y-%m-%d 00:00:00")
    month_end = month_end_date.strftime("%Y-%m-%d 23:59:59")

    today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")
    today_end = datetime.now().strftime("%Y-%m-%d 23:59:59")

    # --------------------
    # 今日登録した商品のみ表示（あなたの現状仕様を維持）
    # --------------------
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

    # ★テンプレートが参照しても落ちないように、必ず初期化して渡す
    prices = None
    cheapest = None          # compare.html が参照してもOKにする
    max_diff = 0             # compare.html が参照してもOKにする
    benefit = 0              # 「★店舗で買うと○円お得！」用
    favorite_store = None    # ★店舗名
    total_saved_month = 0    # 月初〜月末の累計

    # --------------------
    # 月間累計：favorites の各行について
    # (その商品の最大価格 - ★で選ばれた価格) を合計
    # --------------------
    total_saved_month = conn.execute(
        """
        SELECT COALESCE(SUM(
            (SELECT MAX(p2.price) FROM prices p2 WHERE p2.item_id = p.item_id) - p.price
        ), 0) AS total
        FROM favorites f
        JOIN prices p ON p.id = f.price_id
        WHERE f.created_at BETWEEN ? AND ?
        """,
        (month_start, month_end)
    ).fetchone()["total"]

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
            ORDER BY p.price
            """,
            (product_id,)
        ).fetchall()

        if rows:
            # 既存UI用（表のdiffやmax_diffが min基準の可能性が高いので維持）
            min_price = rows[0]["price"]
            max_price = rows[-1]["price"]
            max_diff = max_price - min_price

            prices_list = []
            starred_price = None

            for r in rows:
                diff_vs_min = r["price"] - min_price  # 表示用（従来仕様維持）
                prices_list.append({
                    "price_id": r["price_id"],
                    "store_name": r["store_name"],
                    "price": r["price"],
                    "diff": diff_vs_min,
                    "is_cheapest": diff_vs_min == 0,
                    "is_favorite": bool(r["is_favorite"])
                })

                if r["is_favorite"]:
                    favorite_store = r["store_name"]
                    starred_price = r["price"]

            prices = prices_list
            cheapest = prices_list[0]  # compare.html が参照する用（従来互換）

            # ヘッダー表示用：最大価格 - ★価格
            if starred_price is not None:
                benefit = max_price - starred_price
            else:
                benefit = 0
                favorite_store = None

    conn.close()

    # ★compare.html が期待していそうな変数を「全部」渡す（UndefinedError対策）
    return render_template(
        "compare.html",
        today=today.strftime("%Y/%m/%d"),
        products=products,
        prices=prices,
        selected_product_id=int(product_id) if product_id else None,
        cheapest=cheapest,
        max_diff=max_diff,
        total_saved=total_saved_month,   # 添付の「★1ヶ月累計」の場所
        benefit=benefit,
        favorite_store=favorite_store
    )


# --------------------
# ★切り替え（同一商品で1つだけ）
# --------------------
@app.route("/favorite/<int:price_id>")
def favorite(price_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = get_db_connection()

    # クリックされた price の item_id を取得
    row = conn.execute("SELECT item_id FROM prices WHERE id = ?", (price_id,)).fetchone()
    if not row:
        conn.close()
        return redirect(request.referrer or url_for("compare"))

    item_id = row["item_id"]

    # すでにその price_id が★なら、外す（トグル）
    already = conn.execute("SELECT 1 FROM favorites WHERE price_id = ?", (price_id,)).fetchone()

    if already:
        conn.execute("DELETE FROM favorites WHERE price_id = ?", (price_id,))
    else:
        # 同じ商品の★を全部外す（1つだけ制約）
        conn.execute(
            """
            DELETE FROM favorites
            WHERE price_id IN (SELECT id FROM prices WHERE item_id = ?)
            """,
            (item_id,)
        )
        # 新しく★を付ける
        conn.execute(
            "INSERT INTO favorites (price_id, created_at) VALUES (?, ?)",
            (price_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

    conn.commit()
    conn.close()

    return redirect(request.referrer or url_for("compare"))


# --------------------
# 商品追加
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

        # --- 商品 ---
        item = conn.execute("SELECT id FROM items WHERE name = ?", (item_name,)).fetchone()
        if item:
            item_id = item["id"]
        else:
            cur = conn.execute("INSERT INTO items (name) VALUES (?)", (item_name,))
            item_id = cur.lastrowid

        # --- 店舗 ---
        store = conn.execute("SELECT id FROM stores WHERE name = ?", (shop_name,)).fetchone()
        if store:
            store_id = store["id"]
        else:
            cur = conn.execute("INSERT INTO stores (name) VALUES (?)", (shop_name,))
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


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
