from flask import Flask

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
def hello():
    try:
        conn = conn_db()
        conn.close()
        return 'DB接続成功!'
    except Exception as e:
        return f'DB接続エラー: {e}'

if __name__ == '__main__':
    app.run(debug=True)