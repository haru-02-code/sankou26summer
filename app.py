from flask import Flask,render_template,request,redirect,url_for,jsonify
# mysqlライブラリの読み込み
import mysql.connector

#正規表現のモジュール
import re

# ファイル名を安全にするための何か(後で調べる)
from werkzeug.utils import secure_filename
# WindowsとMacで環境に依存せず正しいパスを組み立てるため
import os
# 日本語の画像ファイルも正しく登録するためにファイル名を安全な英数字で自動生成
import uuid
#.envの読み込み
from dotenv import load_dotenv
load_dotenv()
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')

import requests

from datetime import date

app = Flask(__name__)

#ジャンルを取得する
def load_genre_map(media_type='movie'):
    url = f"https://api.themoviedb.org/3/genre/{media_type}/list"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "ja-JP"
    }
    response = requests.get(url, params=params)
    data = response.json()

    genre_map = {}
    for genre in data['genres']:
        genre_map[genre['id']] = genre['name']

    return genre_map

GENRE_MAP = load_genre_map('movie')
TV_GENRE_MAP = load_genre_map('tv')

EXCLUDED_GENRE_IDS_MOVIE = {99}  # ドキュメンタリー
EXCLUDED_GENRE_IDS_TV = {99, 10763, 10764, 10767}  # ドキュメンタリー, News, Reality, Talk

# print(GENRE_MAP)

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

    if not re.match(r"^([1-9]|[1-9][0-9]|100)$", rating):
        return 'エラー：評価は1〜10の数値で入力してください'

    return None  # エラーがなければNone

def save_tmdb_image(image_path):
    """TMDbの画像パスから、画像をダウンロードして保存し、保存先パスを返す"""
    if not image_path:
        return None

    image_url = "https://image.tmdb.org/t/p/original" + image_path
    response = requests.get(image_url)

    ext = os.path.splitext(image_path)[1]
    filename = uuid.uuid4().hex + ext
    save_path = 'static/uploads/' + filename

    with open(save_path, 'wb') as f:
        f.write(response.content)

    return save_path


# DBになければ登録、あれば取得する関数
def get_or_create_movie(media_type, tmdb_id):
    """
    tmdb_idの作品が自分のDBにあればそのidを返す。
    なければTMDbから取得してINSERTし、新しく作ったidを返す。
    """
    con = conn_db()
    cur = con.cursor()

    cur.execute("select id from movies where tmdb_id = %s", [tmdb_id])
    row = cur.fetchone()

    if row:
        movie_id = row[0]
        cur.close()
        con.close()
        return movie_id

    # まだDBにない場合、TMDbから取得する
    if media_type == 'tv':
        url = f"https://api.themoviedb.org/3/tv/{tmdb_id}"
    else:
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"

    params = {"api_key": TMDB_API_KEY, "language": "ja-JP"}
    response = requests.get(url, params=params)
    data = response.json()

    title = data.get('title') or data.get('name')
    overview = data.get('overview')
    release_date = data.get('release_date') or data.get('first_air_date') or None
    genre_ids = ','.join(str(g['id']) for g in data.get('genres', []))

    poster_path = save_tmdb_image(data.get('poster_path'))
    backdrop_path = save_tmdb_image(data.get('backdrop_path'))

    sql = "insert into movies (tmdb_id, title, overview, poster_path, backdrop_path, release_date, genre_ids) values (%s, %s, %s, %s, %s, %s, %s)"
    cur.execute(sql, [tmdb_id, title, overview, poster_path, backdrop_path, release_date, genre_ids])
    con.commit()

    movie_id = cur.lastrowid

    cur.close()
    con.close()

    return movie_id

@app.route('/')
def index():
    sort = request.args.get('sort', 'name')

    sort_options = {
        'name': 'title asc',
        'date': 'created_at desc',
        'score': 'rating desc'
    }
    order_by = sort_options.get(sort, 'created_at desc')

    con = conn_db()
    cur = con.cursor()

    sql = f"select * from movies order by {order_by}"
    cur.execute(sql)
    movies = cur.fetchall()

    cur.close()
    con.close()

    return render_template("index.html", movies=movies, sort=sort)

#検索用のルート
@app.route('/api/search_movie')
def search_movie():
    query = request.args.get('query')
    media_type = request.args.get('type', 'movie')

    if not query:
        return jsonify([])

    if media_type == 'tv':
        url = "https://api.themoviedb.org/3/search/tv"
        excluded_genre_ids = EXCLUDED_GENRE_IDS_TV
    else:
        url = "https://api.themoviedb.org/3/search/movie"
        excluded_genre_ids = EXCLUDED_GENRE_IDS_MOVIE

    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "ja-JP",
        "include_adult": False
    }

    response = requests.get(url, params=params)
    data = response.json()

    MIN_POPULARITY = 2
    today_str = date.today().isoformat()

    results = []
    for item in data['results']:
        if item.get('adult', False):
            continue
        if item.get('video', False):
            continue
        if item.get('popularity', 0) < MIN_POPULARITY:
            continue

        release = item.get('release_date') or item.get('first_air_date') or ''
        if not release:
            continue
        if release > today_str:
            continue

        if not item.get('overview'):
            continue
        if not item.get('poster_path'):
            continue

        genre_ids = set(item.get('genre_ids', []))
        if genre_ids & excluded_genre_ids:
            continue

        results.append(item)

    return jsonify(results)

#検索画面へのルート
@app.route('/search')
def search():
    return render_template("search.html")


@app.route('/movie/tmdb/<media_type>/<int:tmdb_id>')
def movie_tmdb_detail(media_type, tmdb_id):
    # 常にTMDbから最新情報を取得する
    if media_type == 'tv':
        url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
    else:
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"

    params = {"api_key": TMDB_API_KEY, "language": "ja-JP"}
    response = requests.get(url, params=params)
    data = response.json()

    movie = {
        'tmdb_id': tmdb_id,
        'title': data.get('title') or data.get('name'),
        'overview': data.get('overview'),
        'poster_path': 'https://image.tmdb.org/t/p/w500' + data['poster_path'] if data.get('poster_path') else None,
        'backdrop_path': 'https://image.tmdb.org/t/p/original' + data['backdrop_path'] if data.get('backdrop_path') else None,
        'release_date': data.get('release_date') or data.get('first_air_date'),
        'genres': data.get('genres', [])
    }

    # すでにウォッチリスト・レビューに追加済みか、DBで確認する
    con = conn_db()
    cur = con.cursor()
    cur.execute("select id from movies where tmdb_id = %s", [tmdb_id])
    row = cur.fetchone()

    in_watchlist = False
    review_count = 0
    if row:
        db_movie_id = row[0]
        cur.execute("select count(*) from watchlist where movie_id = %s", [db_movie_id])
        in_watchlist = cur.fetchone()[0] > 0

        cur.execute("select count(*) from reviews where movie_id = %s", [db_movie_id])
        review_count = cur.fetchone()[0]

    cur.close()
    con.close()

    return render_template("movie_detail_new.html", movie=movie, media_type=media_type,
                            in_watchlist=in_watchlist, review_count=review_count)
#ウォッチリスト追加用のルート
@app.route('/watchlist/add', methods=['POST'])
def add_to_watchlist():
    media_type = request.form['media_type']
    tmdb_id = int(request.form['tmdb_id'])

    # 作品をDBに確保する（なければ作る、あれば既存のidを使う）
    movie_id = get_or_create_movie(media_type, tmdb_id)

    con = conn_db()
    cur = con.cursor()

    sql = "insert into watchlist (movie_id) values (%s)"
    cur.execute(sql, [movie_id])
    con.commit()

    cur.close()
    con.close()

    return redirect(url_for('index'))



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
    backdrop = request.files['movie_backdrop']

    # バリデーション関数呼び出し
    error = validate_movie(title, watched_date, rating)
    if error:
        return error

    # ポスター画像
    if image.filename == '':
        image_path = None
    else:
        ext = os.path.splitext(image.filename)[1]
        filename = uuid.uuid4().hex + ext
        save_path = os.path.join('static/uploads', filename)
        image.save(save_path)
        image_path = save_path

    #背景シーン画像
    if backdrop.filename == '':
        backdrop_path = None
    else:
        ext = os.path.splitext(backdrop.filename)[1]
        filename = uuid.uuid4().hex + ext
        save_path = os.path.join('static/uploads', filename)
        backdrop.save(save_path)
        backdrop_path = save_path


    con = conn_db()
    cur = con.cursor()

    sql = "insert into movies (title, genre, watched_date, rating, review, image_path, backdrop_path ) values (%s, %s, %s, %s, %s, %s, %s)"
    #SQLの実行
    cur.execute(sql,[title, genre, watched_date, rating, review, image_path, backdrop_path])
    #データ確定
    con.commit()

    cur.close()
    con.close()

    return redirect(url_for('index'))

#一件だけを取得する
@app.route('/movie/<int:id>')
def detail(id):
    sort = request.args.get('sort', 'name')

    con = conn_db()
    cur = con.cursor()

    sql = "select * from movies where id = %s"
    cur.execute(sql,[id])
    movie = cur.fetchone()

    cur.close()
    con.close()

    return render_template("movie_detail.html", movie=movie, sort=sort)
    


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
    backdrop = request.files['movie_backdrop']

    error = validate_movie(title, watched_date, rating)
    if error:
        return error

    # ポスター画像
    if image.filename == '':
        # 新しい画像が選ばれていない → 既存の画像パスを維持
        con = conn_db()
        cur = con.cursor()
        cur.execute("select image_path from movies where id = %s", [id])
        image_path = cur.fetchone()[0]
        cur.close()
        con.close()
    else:
        ext = os.path.splitext(image.filename)[1]
        filename = uuid.uuid4().hex + ext
        save_path = os.path.join('static/uploads', filename)
        image.save(save_path)
        image_path = save_path

    # 背景シーン画像
    if backdrop.filename == '':
        # 新しい画像が選ばれていない → 既存の画像パスを維持
        con = conn_db()
        cur = con.cursor()
        cur.execute("select backdrop_path from movies where id = %s", [id])
        backdrop_path = cur.fetchone()[0]
        cur.close()
        con.close()
    else:
        ext = os.path.splitext(backdrop.filename)[1]
        filename = uuid.uuid4().hex + ext
        save_path = os.path.join('static/uploads', filename)
        backdrop.save(save_path)
        backdrop_path = save_path

    con = conn_db()
    cur = con.cursor()

    sql = "update movies set title = %s, genre = %s, watched_date = %s, rating = %s, review = %s, image_path = %s, backdrop_path = %s where id = %s"
    cur.execute(sql, [title, genre, watched_date, rating, review, image_path, backdrop_path, id])
    con.commit()

    cur.close()
    con.close()

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)