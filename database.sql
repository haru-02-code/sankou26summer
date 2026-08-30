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
