from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import time
import os
import re

app = Flask(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 MK-MangaBot"}

def proxy_img(url):
    # wsrv.nl proxy to bypass blogger hotlink block
    return f"https://wsrv.nl/?url={url}&w=1200&output=webp"

# ===== SOURCE 1: MANGADEX =====
def get_from_mangadex(url):
    try:
        manga_id = url.split("/title/")[1].split("/")[0]
        manga_res = requests.get(f"https://api.mangadex.org/manga/{manga_id}?includes[]=author&includes[]=cover_art", headers=HEADERS, timeout=15)
        manga = manga_res.json()['data']

        title = manga['attributes']['title'].get('en', 'No Title')
        desc = manga['attributes']['description'].get('en', 'No Description')
        author = next((r['attributes']['name'] for r in manga['relationships'] if r['type']=='author'), 'Unknown')
        cover_file = next((r['attributes']['fileName'] for r in manga['relationships'] if r['type']=='cover_art'), '')
        cover = proxy_img(f"https://uploads.mangadex.org/covers/{manga_id}/{cover_file}") if cover_file else ""
        status = manga['attributes']['status'].title()

        chapters = []
        offset = 0
        while True:
            chap_res = requests.get(f"https://api.mangadex.org/manga/{manga_id}/feed?limit=100&offset={offset}&order[chapter]=asc&translatedLanguage[]=en", headers=HEADERS, timeout=15)
            data = chap_res.json()
            for c in data['data']:
                if c['attributes']['chapter']:
                    chapters.append({'id': c['id'], 'num': c['attributes']['chapter'], 'title': c['attributes']['title'] or f"Chapter {c['attributes']['chapter']}", 'source': 'mangadex'})
            offset += 100
            if offset >= data['total']: break
            time.sleep(0.2)
        return {"title":title,"desc":desc,"author":author,"cover":cover,"status":status,"chapters":chapters}
    except:
        return None

def get_chapter_images_mangadex(chap_id):
    try:
        at_home = requests.get(f"https://api.mangadex.org/at-home/server/{chap_id}", headers=HEADERS, timeout=15).json()
        base = at_home['baseUrl']; hash = at_home['chapter']['hash']
        return [proxy_img(f"{base}/data/{hash}/{p}") for p in at_home['chapter']['data']]
    except: return []

# ===== SOURCE 2: MANGAKALOT =====
def get_from_kakalot(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.find('h1').text.strip()
        cover = proxy_img(soup.find('img', class_='img-loading')['src'])
        desc = soup.find('div', class_='story-detail-info-right').find('p').text.strip()
        author = "Unknown"
        status = "Ongoing"
        chapters = []
        for li in soup.find_all('div', class_='chapter-list')[0].find_all('a'):
            chap_url = li['href']
            chap_num = re.findall(r'chapter-([\d.]+)', chap_url)[0]
            chapters.append({'id': chap_url, 'num': chap_num, 'title': li.text.strip(), 'source': 'kakalot'})
        return {"title":title,"desc":desc,"author":author,"cover":cover,"status":status,"chapters":chapters[::-1]}
    except: return None

def get_chapter_images_kakalot(chap_url):
    try:
        res = requests.get(chap_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        return [proxy_img(img['src']) for img in soup.find_all('img', class_='img-loading')]
    except: return []

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/fetch", methods=["POST"])
def fetch():
    url = request.json.get("url")
    manga = None
    source = ""

    # Try MangaDex first
    if "mangadex.org" in url:
        manga = get_from_mangadex(url)
        source = "mangadex"

    # Fallback to Kakalot
    if not manga:
        manga = get_from_kakalot(url)
        source = "kakalot"

    if not manga:
        return jsonify({"success": False, "error": "Failed to fetch from all sources"})

    manga['source'] = source
    return jsonify({"success": True, **manga})

@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.json
        manga = data['manga']
        selected_ids = data['chapters']
        source = manga['source']

        html = f"""<div class="mk-manga-wrapper"><div class="mk-hero"><img src="{manga['cover']}" class="mk-cover"><div class="mk-info"><h1>{manga['title']}</h1><p><b>Author:</b> {manga['author']} | <b>Status:</b> {manga['status']}</p><p class="mk-desc">{manga['desc']}</p></div></div>"""

        for chap_id in selected_ids:
            chap = next(c for c in manga['chapters'] if c['id']==chap_id)

            # Get images based on source
            if source == 'mangadex':
                pages = get_chapter_images_mangadex(chap_id)
            else:
                pages = get_chapter_images_kakalot(chap_id)

            imgs = "".join([f'<img src="{p}" loading="lazy">' for p in pages])
            html += f"""<div class="mk-chapter"><h3>Chapter {chap['num']}: {chap['title']}</h3><div class="mk-reader">{imgs}</div></div>"""
            time.sleep(1)

        html += """<div class="mk-footer"><p>Powered by MK_BOTS</p></div></div>"""
        html += """<style>.mk-manga-wrapper{max-width:900px;margin:20px auto;background:#0d1117;color:#e6edf3;padding:20px;font-family:Arial;border-radius:12px}
      .mk-hero{display:flex;gap:20px;flex-wrap:wrap}.mk-cover{width:250px;border-radius:8px}
      .mk-info h1{color:#f5c518}.mk-chapter{background:#161b22;padding:20px;margin:20px 0;border-radius:8px}
      .mk-chapter h3{color:#f5c518}.mk-reader img{width:100%;margin:8px 0;border-radius:4px}</style>"""
        return jsonify({"success": True, "code": html})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
