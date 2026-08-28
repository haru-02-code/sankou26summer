from flask import Flask,render_template,request,redirect,url_for
# mysqlライブラリの読み込み
import mysql.connector

#正規表現のモジュール
import re

# ファイル名を安全にするための何か(後で調べる)
from werkzeug.utils import secure_filename
# WindowsとMacで環境に依存せず正しいパスを組み立てるため
import os

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

# バリデーション関数
def validate_movie(title, watched_date, rating):
    if not re.match(r"^.{1,255}$", title):
        return 'エラー：作品名は1文字以上255文字以下で入力してください'

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", watched_date):
        return 'エラー：日付の形式が正しくありません'

    if not re.match(r"^([1-9]|10)$", rating):
        return 'エラー：評価は1〜10の数値で入力してください'

    return None  # エラーがなければNone

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

# 登録
@app.route('/add',methods=['POST'])
def add_movie():
    title = request.form['movie_name'].strip()
    genre = request.form['movie_genre']
    watched_date = request.form['movie_watched_date']
    rating = request.form['movie_rating']
    review = request.form['movie_review']
    image = request.files['movie_image']

    # バリデーション関数呼び出し
    error = validate_movie(title, watched_date, rating)
    if error:
        return error

    if image.filename == '':
        image_path = None
    else:
        filename = secure_filename(image.filename)
        save_path = os.path.join('static/uploads', filename)
        image.save(save_path)
        image_path = save_path


    con = conn_db()
    cur = con.cursor()

    sql = "insert into movies (title, genre, watched_date, rating, review, image_path) values (%s, %s, %s, %s, %s, %s)"
    #SQLの実行
    cur.execute(sql,[title, genre, watched_date, rating, review, image_path])
    #データ確定
    con.commit()

    cur.close()
    con.close()

    return redirect(url_for('index'))

#一件だけを取得する
@app.route('/movie/<int:id>')
def detail(id):
    con = conn_db()
    cur = con.cursor()

    sql = "select * from movies where id = %s"
    cur.execute(sql,[id])
    movie = cur.fetchone()

    cur.close()
    con.close()

    return render_template("movie_detail.html", movie=movie)
    


# 削除
@app.route('/delete/<int:id>',methods=['POST'])
def delete_movie(id):
    con = conn_db()
    cur = con.cursor()

    cur.execute("select image_path from movies where id = %s", [id])
    image_path = cur.fetchone()[0]

    sql = "delete from movies where id = %s"
    cur.execute(sql,[id])
    con.commit()

    cur.close()
    con.close()

    # そのファイルが存在したら物理削除する
    if image_path and os.path.exists(image_path):
        os.remove(image_path)

    return redirect(url_for('index'))

# 編集画面の表示
@app.route('/edit/<int:id>')
def edit_form(id):
    con = conn_db()
    cur = con.cursor()

    sql = "select * from movies where id = %s"
    cur.execute(sql,[id])
    movie = cur.fetchone()

    cur.close()
    con.close()

    return render_template("edit.html", movie=movie)

# 更新
@app.route('/update/<int:id>',methods=['POST'])
def update_movie(id):
    title = request.form['movie_name'].strip()
    genre = request.form['movie_genre']
    watched_date = request.form['movie_watched_date']
    rating = request.form['movie_rating']
    review = request.form['movie_review']
    image = request.files['movie_image']

    error = validate_movie(title, watched_date, rating)
    if error:
        return error

    if image.filename == '':
        # 新しい画像が選ばれていない → 既存の画像パスを維持
        con = conn_db()
        cur = con.cursor()
        cur.execute("select image_path from movies where id = %s", [id])
        image_path = cur.fetchone()[0]
        cur.close()
        con.close()
    else:
        filename = secure_filename(image.filename)
        save_path = os.path.join('static/uploads', filename)
        image.save(save_path)
        image_path = save_path

    con = conn_db()
    cur = con.cursor()

    sql = "update movies set title = %s, genre = %s, watched_date = %s, rating = %s, review = %s, image_path = %s where id = %s"
    cur.execute(sql, [title, genre, watched_date, rating, review, image_path, id])
    con.commit()

    cur.close()
    con.close()

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)