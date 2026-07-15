from flask import Flask, render_template, request, jsonify
import requests
import time

app = Flask(__name__)

MANGADEX_API = "https://api.mangadex.org"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/fetch", methods=["POST"])
def fetch():
    url = request.json.get("url")
    manga_id = url.split("/title/")[1].split("/")[0]

    try:
        # 1. Get Manga Info
        manga_res = requests.get(f"{MANGADEX_API}/manga/{manga_id}?includes[]=author&includes[]=cover_art")
        manga = manga_res.json()['data']

        title = manga['attributes']['title'].get('en', 'No Title')
        desc = manga['attributes']['description'].get('en', 'No Description')
        author = next((r['attributes']['name'] for r in manga['relationships'] if r['type']=='author'), 'Unknown')
        cover_file = next((r['attributes']['fileName'] for r in manga['relationships'] if r['type']=='cover_art'), '')
        cover = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_file}.512.jpg"
        status = manga['attributes']['status']

        # 2. Get Chapters
        chapters = []
        offset = 0
        while True:
            chap_res = requests.get(f"{MANGADEX_API}/manga/{manga_id}/feed?limit=100&offset={offset}&order[chapter]=asc&translatedLanguage[]=en")
            data = chap_res.json()
            for c in data['data']:
                if c['attributes']['chapter']:
                    chapters.append({
                        'id': c['id'],
                        'num': c['attributes']['chapter'],
                        'title': c['attributes']['title'] or f"Chapter {c['attributes']['chapter']}"
                    })
            offset += 100
            if offset >= data['total']: break
            time.sleep(0.5) # Anti-ban

        return jsonify({"success": True, "title": title, "desc": desc, "author": author, "cover": cover, "status": status, "chapters": chapters})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    manga = data['manga']
    selected_ids = data['chapters']

    html = f"""<!-- MK MANGA BLOG by MK_BOTS -->
<div class="mk-manga-wrapper">
  <div class="mk-hero">
    <img src="{manga['cover']}" class="mk-cover">
    <div class="mk-info">
      <h1>{manga['title']}</h1>
      <p><b>Author:</b> {manga['author']} | <b>Status:</b> {manga['status']}</p>
      <p class="mk-desc">{manga['desc']}</p>
    </div>
  </div>"""

    for chap_id in selected_ids[:20]: # Limit 20 per post
        chap = next(c for c in manga['chapters'] if c['id']==chap_id)

        # Get pages
        at_home = requests.get(f"{MANGADEX_API}/at-home/server/{chap_id}").json()
        base = at_home['baseUrl']
        hash = at_home['chapter']['hash']
        pages = [f"{base}/data/{hash}/{p}" for p in at_home['chapter']['data']]

        imgs = "".join([f'<img src="{p}" loading="lazy">' for p in pages])

        html += f"""
  <div class="mk-chapter">
    <h3>Chapter {chap['num']}: {chap['title']}</h3>
    <div class="mk-reader">{imgs}</div>
  </div>"""
        time.sleep(1)

    html += """<div class="mk-footer"><p>Powered by <a href="https://mk-bots.blogspot.com">MK_BOTS</a></p></div></div>
<style>.mk-manga-wrapper{max-width:900px;margin:0 auto;background:#111;color:#fff;padding:20px;font-family:Arial}.mk-hero{display:flex;gap:20px;flex-wrap:wrap}.mk-cover{width:250px;border-radius:8px}.mk-info h1{color:#f5c518}.mk-chapter{background:#1a1a1a;padding:20px;margin:20px 0;border-radius:8px}.mk-reader img{width:100%;margin:5px 0}</style>"""

    return jsonify({"code": html})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
