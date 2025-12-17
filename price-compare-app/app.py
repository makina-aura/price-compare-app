print("### RUNNING APP.PY ###", __file__)


from flask import Flask, render_template, request, redirect, session

app = Flask(__name__)
app.secret_key = "debug-secret-key"


def get_db_connection():
    conn = sqlite3.connect("db/comparison_app.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # ① フォームの中身を確認
        print("DEBUG form =", dict(request.form))

        username = request.form.get("username")
        password = request.form.get("password")
        nickname = request.form.get("nickname")

        print("DEBUG nickname =", nickname)

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE name = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user and user["password"] == password:
            session.clear()
            session["user_id"] = user["user_id"]
            session["nickname"] = nickname

            # ② セッション確認
            print("DEBUG session after login =", dict(session))

            return redirect("/dashboard")

        print("Login incorrect")
        return render_template("login.html", error="ログイン失敗")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    return render_template(
        "dashboard.html",
        nickname=session.get("nickname")
    )

@app.route("/history")
def history():
    conn = get_db()
    items = conn.execute("""
        SELECT
            name,
            store,
            price,
            created_at
        FROM items
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()

    return render_template(
        "history.html",
        items=items
    )


@app.route("/compare")
def compare():
    conn = get_db()
    items = conn.execute("""
        SELECT
            name,
            store,
            price
        FROM items
        ORDER BY name, price
    """).fetchall()
    conn.close()

    return render_template(
        "compare.html",
        items=items
    )



@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name = request.form.get("name")
        store = request.form.get("store")
        price = request.form.get("price")

        conn = get_db()
        conn.execute("""
            INSERT INTO items (name, store, price, created_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (name, store, price))
        conn.commit()
        conn.close()

    return render_template("add.html")

if __name__ == "__main__":
    app.run()





