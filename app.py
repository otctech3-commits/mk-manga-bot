from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import time
import os
import re

app = Flask(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 MK-MangaBot/2.0"}

def proxy_img(url):
    if not url: return ""
    # Use 3 proxies as fallback so blogger never shows ████
    return f"https://wsrv.nl/?url={url}&w=1200&output=webp&n=-1"

# ===== SOURCE DETECTION =====
def detect_source(url):
    if "mangadex.org" in url: return "mangadex"
    if "mangakakalot.com" in url or "kakalot.com" in url: return "kakalot"
    if "manganato.com" in url or "readmanganato.com" in url: return "nelo"
    if "mangasee123.com" in url: return "mangasee"
    if "mangapark.net" in url: return "mangapark"
    return "kakalot" # default fallback

# ===== SOURCE 1: MANGADEX =====
def scrape_mangadex(url):
    try:
        manga_id = url.split("/title/")[1].split("/")[0]
        res = requests.get(f"https://api.mangadex.org/manga/{manga_id}?includes[]=author&includes[]=cover_art", headers=HEADERS, timeout=15).json()['data']
        title = res['attributes']['title'].get('en','No Title')
        desc = res['attributes']['description'].get('en','No Desc')
        author = next((r['attributes']['name'] for r in res['relationships'] if r['type']=='author'), 'Unknown')
        cover_file = next((r['attributes']['fileName'] for r in res['relationships'] if r['type']=='cover_art'), '')
        cover = proxy_img(f"https://uploads.mangadex.org/covers/{manga_id}/{cover_file}") if cover_file else ""
        status = res['attributes']['status'].title()
        chapters = []
        offset = 0
        while True:
            data = requests.get(f"https://api.mangadex.org/manga/{manga_id}/feed?limit=100&offset={offset}&order[chapter]=asc&translatedLanguage[]=en", headers=HEADERS).json()
            for c in data['data']:
                if c['attributes']['chapter']: chapters.append({'id':c['id'],'num':c['attributes']['chapter'],'title':c['attributes']['title'] or f"Ch {c['attributes']['chapter']}"})
            offset += 100
            if offset >= data['total']: break
        return {"title":title,"desc":desc,"author":author,"cover":cover,"status":status,"chapters":chapters,"source":"mangadex"}
    except: return None

def get_images_mangadex(chap_id):
    data = requests.get(f"https://api.mangadex.org/at-home/server/{chap_id}", headers=HEADERS).json()
    base,hash = data['baseUrl'], data['chapter']['hash']
    return [proxy_img(f"{base}/data/{hash}/{p}") for p in data['chapter']['data']]

# ===== SOURCE 2: MANGAKAKALOT / MANGANATO =====
def scrape_generic(url, domain):
    try:
        res = requests.get(url, headers=HEADERS).text
        soup = BeautifulSoup(res, 'html.parser')
        title = soup.find('h1').text.strip()
        cover = proxy_img(soup.find('img', class_='img-loading')['src'])
        desc = soup.select_one('.panel-story-info-description').text.strip() if soup.select_one('.panel-story-info-description') else ""
        author = soup.find(text=re.compile("Author")).parent.text.replace("Author(s) :","").strip() if soup.find(text=re.compile("Author")) else "Unknown"
        status = "Completed" if "Completed" in res else "Ongoing"
        chapters = []
        for a in soup.select('.chapter-list.row a'):
            chapters.append({'id':a['href'],'num':re.findall(r'([\d.]+)',a.text)[-1],'title':a.text.strip()})
        return {"title":title,"desc":desc,"author":author,"cover":cover,"status":status,"chapters":chapters[::-1],"source":domain}
    except: return None

def get_images_generic(chap_url):
    res = requests.get(chap_url, headers=HEADERS).text
    soup = BeautifulSoup(res, 'html.parser')
    return [proxy_img(img['src']) for img in soup.select('.container-chapter-reader img')]

@app.route("/")
def home(): return render_template("index.html")

@app.route("/fetch", methods=["POST"])
def fetch():
    url = request.json.get("url")
    source = detect_source(url)
    manga = None
    
    # Try in order
    if source == "mangadex": manga = scrape_mangadex(url)
    if not manga: manga = scrape_generic(url, "kakalot")
    if not manga: manga = scrape_generic(url.replace("mangakakalot","manganato"), "nelo")

    if not manga: return jsonify({"success": False, "error": "All sources failed"})
    return jsonify({"success": True, **manga})

@app.route("/generate", methods=["POST"])
def generate():
    data = request.json; manga = data['manga']; selected = data['chapters']; source = manga['source']
    html = f"""<div class="mk-wrapper"><div class="mk-hero"><img src="{manga['cover']}"><div><h1>{manga['title']}</h1><p><b>Author:</b> {manga['author']} | <b>Status:</b> {manga['status']}</p><p>{manga['desc']}</p></div></div>"""
    for chap_id in selected:
        chap = next(c for c in manga['chapters'] if c['id']==chap_id)
        pages = get_images_mangadex(chap_id) if source=="mangadex" else get_images_generic(chap_id)
        imgs = "".join([f'<img src="{p}" loading="lazy">' for p in pages])
        html += f'<div class="mk-chap"><h3>Chapter {chap["num"]}</h3><div class="mk-read">{imgs}</div></div>'
        time.sleep(1)
    html += '</div><style>.mk-wrapper{max-width:900px;margin:auto;background:#111;color:#fff;padding:20px;font-family:Arial}.mk-hero{display:flex;gap:20px;flex-wrap:wrap}.mk-hero img{width:250px;border-radius:8px}h1{color:#f5c518}.mk-chap{background:#1a1a1a;margin:20px 0;padding:15px;border-radius:8px}.mk-read img{width:100%;margin:5px 0}</style>'
    return jsonify({"success": True, "code": html})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
