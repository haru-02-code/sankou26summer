from flask import Flask,render_template,request,redirect

# mysqlライブラリの読み込み
import mysql.connector

app = Flask(__name__)

# データベース接続設定
def conn_db():
    conn = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="root",
        database="sankou26s",
        charset="utf8mb4"
    )
    return conn

@app.route('/')
def index():
    con = conn_db()
    cur = con.cursor()

    sql = "select * from movies"
    cur.execute(sql)
    movies = cur.fetchall()

    cur.close()
    con.close()

    return render_template("index.html", movies=movies)

@app.route('/add.html') 
def add_form():
    return render_template("add.html")

@app.route('/add',methods=['POST'])
def add_movie():
    title = request.form['movie_name']
    genre = request.form['movie_genre']
    watched_date = request.form['movie_watched_date']
    rating = request.form['movie_rating']
    review = request.form['movie_review']

    con = conn_db()
    cur = con.cursor()

    sql = "insert into movies (title, genre, watched_date, rating, review) values (%s, %s, %s, %s, %s)"
    #SQLの実行
    cur.execute(sql,[title, genre, watched_date, rating, review])
    #データ確定
    con.commit()

    cur.close()
    con.close()

    return '登録できました！'

if __name__ == '__main__':
    app.run(debug=True)