from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

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

@app.route("/history")
def history():
    return render_template("history.html")

if __name__ == "__main__":
    app.run(debug=True)
