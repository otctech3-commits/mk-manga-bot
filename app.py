from flask import Flask, render_template, request, jsonify
import requests
import time
import os

app = Flask(__name__)
MANGADEX_API = "https://api.mangadex.org"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/fetch", methods=["POST"])
def fetch():
    try:
        url = request.json.get("url")
        manga_id = url.split("/title/")[1].split("/")[0]

        # Get manga info
        manga_res = requests.get(f"{MANGADEX_API}/manga/{manga_id}?includes[]=author&includes[]=cover_art", timeout=15)
        manga_data = manga_res.json()['data']

        title = manga_data['attributes']['title'].get('en', 'No Title')
        desc = manga_data['attributes']['description'].get('en', 'No Description Available')
        author = next((r['attributes']['name'] for r in manga_data['relationships'] if r['type']=='author'), 'Unknown')
        cover_file = next((r['attributes']['fileName'] for r in manga_data['relationships'] if r['type']=='cover_art'), '')
        cover = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_file}.512.jpg" if cover_file else ""
        status = manga_data['attributes']['status'].title()

        # Get all chapters
        chapters = []
        offset = 0
        while True:
            chap_res = requests.get(f"{MANGADEX_API}/manga/{manga_id}/feed?limit=100&offset={offset}&order[chapter]=asc&translatedLanguage[]=en&includes[]=scanlation_group", timeout=15)
            data = chap_res.json()
            for c in data['data']:
                if c['attributes']['chapter']:
                    chapters.append({
                        'id': c['id'],
                        'num': c['attributes']['chapter'],
                        'title': c['attributes']['title'] or f"Chapter {c['attributes']['chapter']}"
                    })
            offset += 100
            if offset >= data['total']:
                break
            time.sleep(0.3)

        return jsonify({"success": True, "title": title, "desc": desc, "author": author, "cover": cover, "status": status, "chapters": chapters})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.json
        manga = data['manga']
        selected_ids = data['chapters']

        # Header + Cover
        html = f"""<!-- MK MANGA BOT v2.0 -->
<div class="mk-manga-wrapper">
    <div class="mk-hero">
        <img src="{manga['cover']}" class="mk-cover" alt="{manga['title']}">
        <div class="mk-info">
            <h1>{manga['title']}</h1>
            <p><b>Author:</b> {manga['author']} | <b>Status:</b> {manga['status']}</p>
            <p class="mk-desc">{manga['desc']}</p>
        </div>
    </div>"""

        # Loop chapters and get images with proxy to avoid CORS
        for chap_id in selected_ids:
            chap = next(c for c in manga['chapters'] if c['id']==chap_id)

            # Get chapter images from MangaDex@Home
            at_home = requests.get(f"{MANGADEX_API}/at-home/server/{chap_id}", timeout=15).json()
            base = at_home['baseUrl']
            hash = at_home['chapter']['hash']

            # Use proxy so Blogger can load images
            pages = []
            for p in at_home['chapter']['data']:
                img_url = f"{base}/data/{hash}/{p}"
                proxy_url = f"https://mangadex.org/_next/image?url={img_url}&w=1920&q=75"
                pages.append(f'<img src="{proxy_url}" loading="lazy" alt="Page">')

            imgs = "".join(pages)
            html += f"""<div class="mk-chapter"><h3>Chapter {chap['num']}: {chap['title']}</h3><div class="mk-reader">{imgs}</div></div>"""
            time.sleep(0.8) # avoid rate limit

        html += """<div class="mk-footer"><p>Read more at <a href="https://mk-playz.blogspot.com" style="color:#f5c518">MK_PLAYZ</a></p></div></div>"""

        # CSS
        html += """<style>
       .mk-manga-wrapper{max-width:900px;margin:20px auto;background:#0d1117;color:#e6edf3;padding:20px;font-family:Arial;border-radius:12px}
       .mk-hero{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:30px}
       .mk-cover{width:250px;border-radius:8px;box-shadow:0 4px 15px rgba(0,0,0,0.5)}
       .mk-info h1{color:#f5c518;margin-top:0}
       .mk-desc{line-height:1.6;color:#b1bac4}
       .mk-chapter{background:#161b22;padding:20px;margin:20px 0;border-radius:8px;border:1px solid #30363d}
       .mk-chapter h3{color:#f5c518;border-bottom:1px solid #30363d;padding-bottom:10px}
       .mk-reader img{width:100%;margin:8px 0;border-radius:4px}
       .mk-footer{text-align:center;margin-top:30px;padding-top:20px;border-top:1px solid #30363d;color:#8b949e}
        @media(max-width:768px){.mk-hero{flex-direction:column}.mk-cover{width:100%}}
        </style>"""

        return jsonify({"success": True, "code": html})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
