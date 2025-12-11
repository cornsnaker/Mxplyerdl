import aiohttp
import re
import json
from urllib.parse import urljoin, urlparse
from config import USER_AGENT, ORIGIN

async def fetch(url, headers=None):
    if headers is None:
        headers = {
            "User-Agent": USER_AGENT,
            "Origin": ORIGIN,
            "Referer": ORIGIN # Default referer
        }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
    return ""

def extract_metadata_from_jsonld(html):
    pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
    for m in re.finditer(pattern, html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                for item in data:
                    if item.get('@type') in ['Episode', 'Movie']:
                        return item
        except:
            continue
    return None

def extract_title(html):
    data = extract_metadata_from_jsonld(html)
    if data:
        if data.get('@type') == 'Episode':
            series = data.get('partOfSeries')
            if series and series.get('name'):
                return series['name']
        elif data.get('@type') == 'Movie':
            return data.get('name')

    m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if m: return m.group(1)
    m = re.search(r"<title>([^<]+)</title>", html)
    if m: return m.group(1)
    return "Unknown"

def extract_thumbnail(html):
    data = extract_metadata_from_jsonld(html)
    if data:
        image = data.get('image')
        if isinstance(image, list) and len(image) > 0:
            return image[0]
        if isinstance(image, str):
            return image

    m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    if m: return m.group(1)
    return None

def extract_season_episode(html):
    data = extract_metadata_from_jsonld(html)
    s, e = None, None
    if data and data.get('@type') == 'Episode':
        s_info = data.get('partOfSeason')
        s = s_info.get('seasonNumber') if s_info else None
        e = data.get('episodeNumber')

    if s is None:
        m = re.search(r'"season"\s*:\s*(\d+)', html)
        if m: s = int(m.group(1))
    if e is None:
        m = re.search(r'"episode"\s*:\s*(\d+)', html)
        if m: e = int(m.group(1))

    return s or 0, e or 0

async def gather_episode_links(url, html):
    found = set()
    # Regex from original mx.py
    for m in re.findall(r'(/detail/(?:episode|movie)/[a-zA-Z0-9\-\?_=&]+)', html):
        u = urljoin("https://www.mxplayer.in", m.split('"')[0])
        found.add(u.split("?")[0])

    for m in re.findall(r'(/show/watch-[^"\'\s<>]+)', html):
        u = urljoin("https://www.mxplayer.in", m)
        found.add(u.split("?")[0])

    return sorted(list(found))

async def get_m3u8(html):
    # Same logic as mx.py
    m = re.search(r'(https?://[^"\']+?\.m3u8[^"\']*)', html)
    if m: return m.group(1)
    m = re.search(r'(https?:\\\\/\\\\/[^"]+?\.m3u8[^"]*)', html)
    if m: return m.group(1).replace("\\/", "/").replace("\\\\/", "/")
    m = re.search(r'streamUrl"\s*:\s*"([^"]+?\.m3u8[^"]*)"', html)
    if m: return m.group(1)
    return None

async def parse_master_playlist(m3u8_text):
    variants = []
    lines = m3u8_text.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith("#EXT-X-STREAM-INF"):
            # Simple parsing for bandwidth and resolution
            bw = 0
            res = None
            m_bw = re.search(r'BANDWIDTH=(\d+)', line)
            if m_bw: bw = int(m_bw.group(1))
            m_res = re.search(r'RESOLUTION=(\d+x\d+)', line)
            if m_res: res = m_res.group(1)

            # Get URI
            j = i+1
            uri = None
            while j < len(lines):
                if lines[j].strip() and not lines[j].startswith("#"):
                    uri = lines[j].strip()
                    break
                j += 1

            if uri:
                variants.append({'bandwidth': bw, 'resolution': res, 'uri': uri})
    return variants
