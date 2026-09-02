-- データベース作成
CREATE DATABASE sankou26s CHARACTER SET utf8mb4;
USE sankou26s;

-- テーブル作成
CREATE TABLE movies (
    id int primary key auto_increment,          -- 主キー、自動増加
    title varchar(255) NOT NULL,       -- 作品名
    genre varchar(50),                -- ジャンル
    watched_date date,         -- 視聴日（日付型）
    rating int,               -- 評価（整数）
    review text,               -- 感想（長文になる可能性あり）
    image_path varchar(255),           -- 画像パス
    backdrop_path varchar(255),         --背景シーン画像パス         
    created_at datetime DEFAULT CURRENT_TIMESTAMP,
    updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4;

-- 新規で作るDB
-- movies（作品カタログ／TMDbのキャッシュ）
CREATE TABLE movies (
    id int primary key auto_increment,
    tmdb_id int unique,
    media_type varchar(10),
    title varchar(255) NOT NULL,
    overview text,
    poster_path varchar(255),
    backdrop_path varchar(255),
    release_date date,
    genre_ids varchar(255),
    created_at datetime DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4;

-- watchlist（観たい作品リスト）
CREATE TABLE watchlist (
    id int PRIMARY KEY auto_increment,
    movie_id int,
    added_at datetime DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (movie_id) REFERENCES movies(id)
) CHARACTER SET utf8mb4;

-- reviews（視聴ログ／旧movies相当
CREATE TABLE reviews (
    id int primary key auto_increment, 
    movie_id int,        
    watched_date date,         -- 視聴日（日付型）
    rating int,               -- 評価（整数）
    review text,               -- 感想（長文になる可能性あり
    created_at datetime DEFAULT CURRENT_TIMESTAMP,
    updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (movie_id) REFERENCES movies(id)
) CHARACTER SET utf8mb4;


考えるヒント:

movie_idは、movies.idを参照する「外部キー」です。今までのテーブルにはなかった概念ですが、まずは普通のint型のカラムとして作るだけでも動きます（本格的な外部キー制約FOREIGN KEYを付けるかどうかは、余裕があれば検討しましょう)
reviewsテーブルのratingは、以前「100点満点」に変更した経緯があるので、型やチェック方法もそれを踏まえてください
文字コード（CHARACTER SET utf8mb4）は、3つのテーブル全てに付け忘れないようにしてください
