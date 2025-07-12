from flask import Flask, render_template_string
import os
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# === Data-fetching functions (reuse or import from your module) ===
def get_spotify_top20(sp_client, playlist_id="37i9dQZEVXbLnolsZ8PSNw"):
    results = sp_client.playlist_items(playlist_id, fields='items.track(name,artists(name))', limit=20)
    return [{'title': item['track']['name'],
             'artist': ', '.join([a['name'] for a in item['track']['artists']])}
            for item in results['items']]

def get_official_charts_top20():
    url = "https://www.officialcharts.com/charts/singles-chart/"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    items = soup.select_one('ol.chart-positions').select('li')[:20]
    return [{'title': i.select_one('div.title').text.strip(),
             'artist': i.select_one('div.artist').text.strip()}
            for i in items]

def get_tiktok_trending_top20(rapidapi_key):
    url = "https://tiktok-trends.p.rapidapi.com/trending/audio"
    headers = {'x-rapidapi-host': "tiktok-trends.p.rapidapi.com",
               'x-rapidapi-key': rapidapi_key}
    resp = requests.get(url, headers=headers, params={'region':'GB','limit':20})
    return [{'title': e['title'], 'artist': e['author']} for e in resp.json().get('audios', [])]

def get_bbc_radio1_top40():
    url = "https://www.bbc.co.uk/programmes/b006wrzs/episodes/player#play"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    items = soup.select('ul.chart-list li')[:20]
    return [{'title': i.select_one('.chart-item__title').text.strip(),
             'artist': i.select_one('.chart-item__artist').text.strip()}
            for i in items]

# === Templates ===
INDEX_HTML = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Weekly Top 20 Tracks</title>
  <style>
    body { font-family: sans-serif; margin: 20px; }
    .container { display: flex; flex-wrap: wrap; gap: 20px; }
    .box { border: 1px solid #ccc; border-radius: 8px; padding: 10px; width: 300px; }
    .box h2 { margin-top: 0; }
    .box ol { padding-left: 20px; }
    nav a { margin-right: 10px; }
  </style>
</head>
<body>
  <nav><a href="/">Home</a> | <a href="/stats">Statistics</a></nav>
  <h1>Weekly Top 20 Tracks by Source</h1>
  <div class="container">
    {% for source, tracks in data.items() %}
    <div class="box">
      <h2>{{ source }}</h2>
      <ol>
        {% for t in tracks %}
        <li>{{ t.title }}<br><small>{{ t.artist }}</small></li>
        {% endfor %}
      </ol>
    </div>
    {% endfor %}
  </div>
</body>
</html>
'''

STATS_HTML = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Track Statistics</title>
  <style>
    body { font-family: sans-serif; margin: 20px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; }
    th { background-color: #f4f4f4; }
    nav a { margin-right: 10px; }
  </style>
</head>
<body>
  <nav><a href="/">Home</a> | <a href="/stats">Statistics</a></nav>
  <h1>Aggregated Track Statistics</h1>
  <table>
    <thead>
      <tr><th>Rank</th><th>Title</th><th>Artist</th><th>Appearances</th></tr>
    </thead>
    <tbody>
      {% for idx, track in enumerate(stats, 1) %}
      <tr>
        <td>{{ idx }}</td>
        <td>{{ track.title }}</td>
        <td>{{ track.artist }}</td>
        <td>{{ track.count }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
'''

# === Aggregation ===
def aggregate(tracks_by_source):
    tally = {}
    for source, lst in tracks_by_source.items():
        for t in lst:
            key = (t['title'].lower(), t['artist'].lower())
            if key not in tally:
                tally[key] = {'title': t['title'], 'artist': t['artist'], 'count': 0}
            tally[key]['count'] += 1
    return sorted(tally.values(), key=lambda x: -x['count'])[:20]

@app.route('/')
def home():
    # Credentials
    sp = Spotify(client_credentials_manager=SpotifyClientCredentials(
            client_id=os.getenv('SPOTIPY_CLIENT_ID'),
            client_secret=os.getenv('SPOTIPY_CLIENT_SECRET')))
    rapidapi = os.getenv('RAPIDAPI_KEY')

    data = {
        'Spotify UK Top50 (Top20)': get_spotify_top20(sp),
        'Official UK Singles': get_official_charts_top20(),
        'TikTok Trending UK': get_tiktok_trending_top20(rapidapi),
        'BBC Radio1 Top40': get_bbc_radio1_top40()
    }
    return render_template_string(INDEX_HTML, data=data)

@app.route('/stats')
def stats():
    # reuse home-fetch
    sp = Spotify(client_credentials_manager=SpotifyClientCredentials(
            client_id=os.getenv('SPOTIPY_CLIENT_ID'),
            client_secret=os.getenv('SPOTIPY_CLIENT_SECRET')))
    rapidapi = os.getenv('RAPIDAPI_KEY')
    sources = {
        'Spotify': get_spotify_top20(sp),
        'Official': get_official_charts_top20(),
        'TikTok': get_tiktok_trending_top20(rapidapi),
        'BBC': get_bbc_radio1_top40()
    }
    stats = aggregate(sources)
    return render_template_string(STATS_HTML, stats=stats)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
