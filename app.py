from flask import Flask,render_template,request,redirect,url_for,jsonify,session
# mysqlライブラリの読み込み
import mysql.connector

#正規表現のモジュール
import re

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

# 暗号化キーの設定
app.secret_key = '2026sssankou'

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

    try:
        cur.execute("select id from movies where tmdb_id = %s", [tmdb_id])
        row = cur.fetchone()

        if row:
            movie_id = row[0]
            return movie_id

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

        sql = "insert into movies (tmdb_id, media_type, title, overview, poster_path, backdrop_path, release_date, genre_ids) values (%s, %s, %s, %s, %s, %s, %s, %s)"
        cur.execute(sql, [tmdb_id, media_type, title, overview, poster_path, backdrop_path, release_date, genre_ids])
        con.commit()

        return cur.lastrowid

    except mysql.connector.IntegrityError:
        # ほぼ同時に、別の処理が先にINSERTしていた場合（競合状態）
        con.rollback()
        cur.execute("select id from movies where tmdb_id = %s", [tmdb_id])
        row = cur.fetchone()
        return row[0] if row else None

    finally:
        cur.close()
        con.close()

    return movie_id

# index(log画面)
@app.route('/')
def index():
    sort = request.args.get('sort', 'name')

    sort_options = {
        'name': 'movies.title asc',
        'date': 'reviews.created_at desc',
        'score': 'reviews.rating desc'
    }
    order_by = sort_options.get(sort, 'reviews.created_at desc')

    con = conn_db()
    cur = con.cursor()

    sql = f"""
        select reviews.id, movies.title, movies.poster_path, reviews.rating,
               reviews.watched_date, reviews.created_at, movies.tmdb_id, movies.media_type
        from reviews
        join movies on reviews.movie_id = movies.id
        order by {order_by}
    """
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

        #あらすじなのを除外はやめた方がいいかも    
        # if not item.get('overview'):
        #     continue
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
    from_page = request.args.get('from', 'search')
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

    is_new_movie = row is None

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

    return render_template("movie_detail.html", movie=movie, media_type=media_type,
                            in_watchlist=in_watchlist, review_count=review_count,
                            today=date.today().isoformat(), from_page=from_page, is_new_movie=is_new_movie)

#ウォッチリスト追加用のルート
@app.route('/watchlist/add', methods=['POST'])
def add_to_watchlist():
    media_type = request.form['media_type']
    tmdb_id = int(request.form['tmdb_id'])
    from_page = request.form.get('from', '')

    # 作品をDBに確保する（なければ作る、あれば既存のidを使う）
    movie_id = get_or_create_movie(media_type, tmdb_id)

    con = conn_db()
    cur = con.cursor()

    sql = "insert into watchlist (movie_id) values (%s)"
    cur.execute(sql, [movie_id])
    con.commit()

    cur.close()
    con.close()

    if from_page == 'ajax':
        return jsonify({'status': 'ok'})

    return redirect(url_for('watchlist'))

# ウォッチリスト参照用のルート
@app.route('/watchlist')
def watchlist():
    sort = request.args.get('sort', 'name')

    sort_options = {
        'name': 'movies.title asc',
        'date': 'watchlist.added_at desc'
    }
    order_by = sort_options.get(sort, 'watchlist.added_at desc')

    con = conn_db()
    cur = con.cursor()

    sql = f"""
        select watchlist.id, movies.title, movies.poster_path,
               watchlist.added_at, movies.tmdb_id, movies.media_type
        from watchlist
        join movies on watchlist.movie_id = movies.id
        order by {order_by}
    """
    cur.execute(sql)
    movies = cur.fetchall()

    cur.close()
    con.close()

    # 直前に削除があれば、その情報を取り出す（一度取り出したら、セッションからは消す）
    undo_info = None
    if 'undo_tmdb_id' in session:
        undo_info = {
            'tmdb_id': session.pop('undo_tmdb_id'),
            'media_type': session.pop('undo_media_type'),
            'title': session.pop('undo_title')
        }

    return render_template("watchlist.html", movies=movies, sort=sort, undo_info=undo_info)


# ウォッチリスト削除用ルート
@app.route('/watchlist/remove', methods=['POST'])
def remove_from_watchlist():
    tmdb_id = int(request.form['tmdb_id'])
    from_page = request.form.get('from', '')

    con = conn_db()
    cur = con.cursor()

    cur.execute("select id, title, media_type from movies where tmdb_id = %s", [tmdb_id])
    row = cur.fetchone()

    if row:
        movie_id, title, media_type = row
        cur.execute("delete from watchlist where movie_id = %s", [movie_id])
        con.commit()

        # ウォッチリスト画面からの削除なら、元に戻すための情報をセッションに保存
        if from_page == 'watchlist':
            session['undo_tmdb_id'] = tmdb_id
            session['undo_media_type'] = media_type
            session['undo_title'] = title

    cur.close()
    con.close()

    if from_page == 'ajax':
        return jsonify({'status': 'ok'})

    if from_page == 'watchlist':
        return redirect(url_for('watchlist'))
    elif from_page == 'mylog':
        return redirect(url_for('index'))
    else:
        return redirect(request.referrer or url_for('index'))

# ウォッチリスト削除通知バー機能
@app.route('/watchlist/undo', methods=['POST'])
def undo_watchlist_remove():
    media_type = request.form['media_type']
    tmdb_id = int(request.form['tmdb_id'])

    movie_id = get_or_create_movie(media_type, tmdb_id)

    con = conn_db()
    cur = con.cursor()

    sql = "insert into watchlist (movie_id) values (%s)"
    cur.execute(sql, [movie_id])
    con.commit()

    cur.close()
    con.close()

    return redirect(url_for('watchlist'))

# reviews追加用ルート
@app.route('/reviews/add', methods=['POST'])
def add_review():
    media_type = request.form['media_type']
    tmdb_id = int(request.form['tmdb_id'])
    watched_date = request.form['watched_date']
    rating = request.form['rating']
    review = request.form['review']

    # バリデーション（作品名の代わりに、視聴日・スコアだけチェックする）
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", watched_date):
        return 'エラー：日付の形式が正しくありません'
    if not re.match(r"^([1-9]|[1-9][0-9]|100)$", rating):
        return 'エラー：評価は1〜100の数値で入力してください'

    # 未来の日付でないか、サーバー側でも確認する
    if watched_date > date.today().isoformat():
        return 'エラー：視聴日は今日以前の日付を選んでください'

    # 作品をDBに確保する
    movie_id = get_or_create_movie(media_type, tmdb_id)

    con = conn_db()
    cur = con.cursor()

    sql = "insert into reviews (movie_id, watched_date, rating, review) values (%s, %s, %s, %s)"
    cur.execute(sql, [movie_id, watched_date, rating, review])
    con.commit()

    cur.close()
    con.close()

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)