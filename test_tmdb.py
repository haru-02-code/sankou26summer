# import requests
# from dotenv import load_dotenv
# import os

# import json

# load_dotenv()
# TMDB_API_KEY = os.environ.get('TMDB_API_KEY')

# url = "https://api.themoviedb.org/3/search/movie"
# params = {
#     "api_key": TMDB_API_KEY,
#     "query": "君の名は",
#     "language": "ja-JP"
# }

# response = requests.get(url, params=params)
# data = response.json()

# print(json.dumps(data['results'][0], indent=2, ensure_ascii=False))


import requests
from dotenv import load_dotenv
import os

load_dotenv()
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')

url = "https://api.themoviedb.org/3/genre/movie/list"
params = {
    "api_key": TMDB_API_KEY,
    "language": "ja-JP"
}

response = requests.get(url, params=params)
data = response.json()

print(data)