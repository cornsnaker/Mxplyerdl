#!/usr/bin/env python3
"""
MX Player Auto Downloader (safe, non-DRM only)
Usage:
    python mx_auto_downloader.py cookies.txt <mx_url1> [<mx_url2> ...]
    OR
    python mx_auto_downloader.py cookies.txt --urls-file urls.txt

Requirements:
    pip install requests

Place N_m3u8DL-RE in PATH or edit NM3U8DL_BIN variable below.
"""

import sys
import re
import os
import json
import subprocess
from urllib.parse import urljoin, urlparse
from datetime import datetime
import requests

# ----------------- CONFIG -----------------
NM3U8DL_BIN = "N_m3u8DL-RE"   # change this if binary path differs
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36"
ORIGIN = "https://www.mxplayer.in"
TIMEOUT = 15
# ------------------------------------------

def read_cookies_netscape(path):
    """Parse Netscape cookies.txt -> returns cookie header string"""
    cookies = []
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                name = parts[5].strip()
                value = parts[6].strip()
                cookies.append(f"{name}={value}")
    return "; ".join(cookies)

def fetch(url, cookies_header, referer=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": cookies_header,
        "Origin": ORIGIN,
    }
    if referer:
        headers["Referer"] = referer
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[!] HTTP error fetching {url}: {e}")
        return ""

def extract_metadata_from_jsonld(html):
    """Parses application/ld+json block to extract series/movie info."""
    pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
    # Use finditer to check all blocks
    for m in re.finditer(pattern, html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            # Normalize to list
            if isinstance(data, dict):
                data = [data]

            if isinstance(data, list):
                for item in data:
                    if item.get('@type') in ['Episode', 'Movie']:
                        return item
        except Exception:
            continue
    return None

def extract_title(html):
    # Try JSON-LD first
    data = extract_metadata_from_jsonld(html)
    if data:
        if data.get('@type') == 'Episode':
            series = data.get('partOfSeries')
            if series and series.get('name'):
                return clean_filename(series['name'])
        elif data.get('@type') == 'Movie':
            name = data.get('name')
            if isinstance(name, list) and len(name) > 0:
                first = name[0]
                if isinstance(first, dict):
                    return clean_filename(first.get('@value', 'Unknown'))
                elif isinstance(first, str):
                    return clean_filename(first)
            elif isinstance(name, str):
                return clean_filename(name)

    # Try og:title, then <title>, else None
    m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if m:
        return clean_filename(m.group(1))
    m = re.search(r"<title>([^<]+)</title>", html)
    if m:
        return clean_filename(m.group(1))
    return None

def clean_filename(s):
    # Remove problematic chars
    s = re.sub(r'[\r\n]+', ' ', s)
    s = re.sub(r'[\\/:"*?<>|]+', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.replace(" ", ".")
    return s

def gather_episode_links_from_html(html):
    # Heuristic: find /detail/episode/... and /detail/movie/...
    found = set()
    for m in re.findall(r'(/detail/(?:episode|movie)/[a-zA-Z0-9\-\?_=&]+)', html):
        url = urljoin("https://www.mxplayer.in", m.split('"')[0])
        found.add(url.split("?")[0])  # normalize strip query
    # Also search for JSON blocks with "episodeId" or "detailUrl"
    for m in re.findall(r'https://www\.mxplayer\.in/detail/(?:episode|movie)/[a-zA-Z0-9\-\?=&]+', html):
        found.add(m.split("?")[0])
    return sorted(found)

def find_m3u8_in_text(text):
    # Try direct plain links
    m = re.search(r'(https?://[^"\']+?\.m3u8[^"\']*)', text)
    if m:
        return m.group(1)
    # escaped JSON style
    m = re.search(r'(https?:\\\\/\\\\/[^"]+?\.m3u8[^"]*)', text)
    if m:
        return m.group(1).replace("\\/", "/").replace("\\\\/", "/")
    # streamUrl":"...m3u8"
    m = re.search(r'streamUrl"\s*:\s*"([^"]+?\.m3u8[^"]*)"', text)
    if m:
        return m.group(1)
    # playerUrl or videoURL patterns
    m = re.search(r'"(https?://[^"]+?/master[^"]+?\.m3u8[^"]*)"', text)
    if m:
        return m.group(1)
    return None

def parse_master_playlist(m3u8_text):
    """
    Returns variants list and audio tracks (if any)
    variants: list of dicts {uri, bandwidth(int), resolution=(w,h) or None}
    audio_tracks: list e.g. [{'group_id':'audio-a','language':'en','name':'English','uri':...}, ...]
    """
    variants = []
    audio_tracks = []
    lines = m3u8_text.splitlines()
    last_inf = None
    for i, line in enumerate(lines):
        line=line.strip()
        if line.startswith("#EXT-X-STREAM-INF"):
            # parse attributes
            attrs = parse_attr_list(line[len("#EXT-X-STREAM-INF:"):])
            last_inf = attrs
            # next non-empty non-comment line should be the URI
            j = i+1
            while j < len(lines):
                l = lines[j].strip()
                if l and not l.startswith("#"):
                    uri = l
                    break
                j += 1
            else:
                uri = None
            variants.append({
                "uri": uri,
                "bandwidth": int(attrs.get("BANDWIDTH", 0)),
                "resolution": tuple(map(int, attrs["RESOLUTION"].split("x"))) if "RESOLUTION" in attrs else None,
                "audio": attrs.get("AUDIO")
            })
        elif line.startswith("#EXT-X-MEDIA") and "TYPE=AUDIO" in line:
            attrs = parse_attr_list(line[len("#EXT-X-MEDIA:"):])
            audio_tracks.append({
                "group_id": attrs.get("GROUP-ID"),
                "language": attrs.get("LANGUAGE") or attrs.get("LANG"),
                "name": attrs.get("NAME"),
                "uri": attrs.get("URI"),
            })
    return variants, audio_tracks

def parse_attr_list(s):
    # crude parser for comma-separated key=value pairs, values may be quoted
    out = {}
    # regex to match KEY=VALUE or KEY="VALUE"
    for m in re.finditer(r'([A-Z0-9\-]+)=("([^"]*)"|[^,]*)', s):
        k = m.group(1)
        v = m.group(3) if m.group(3) is not None else m.group(2)
        out[k] = v
    return out

def choose_best_variant(variants):
    # prefer highest resolution height, fallback to bandwidth
    if not variants:
        return None
    def score(v):
        if v["resolution"]:
            return v["resolution"][1] * 1000000 + v["bandwidth"]
        return v["bandwidth"]
    return max(variants, key=score)

def get_quality_label(variant):
    if variant is None:
        return "unknown"
    if variant.get("resolution"):
        return f"{variant['resolution'][1]}p"
    if variant.get("bandwidth"):
        bw=int(variant["bandwidth"])
        if bw>=5000000: return "1080p"
        if bw>=2500000: return "720p"
        if bw>=1000000: return "480p"
        return "360p"
    return "unknown"

def detect_audio_type(variants, audio_tracks, base_url, cookies_header):
    """
    Determine audio type label:
      - If audio_tracks present with multiple languages -> Multi or list languages
      - If variant contains audio groups -> use that info
      - If master playlist has multiple audio URIs -> Dual/Multi
    """
    # check audio_tracks languages
    langs = []
    for a in audio_tracks:
        if a.get("language"):
            langs.append(a["language"])
        elif a.get("name"):
            langs.append(a["name"])
    if langs:
        langs = list(dict.fromkeys(langs))
        if len(langs) == 1:
            return langs[0]
        else:
            return "Multi-" + "-".join(langs)
    # fallback: fetch the chosen variant's playlist and search for ALTERNATE-AUDIO lines or language hints
    if variants:
        uris = [v["uri"] for v in variants if v["uri"]]
        # try to fetch each variant and look for "NAME" or "LANGUAGE" hints
        for uri in uris[:3]:
            if not uri:
                continue
            uri_full = uri if uri.startswith("http") else urljoin(base_url, uri)
            try:
                txt = requests.get(uri_full, headers={"User-Agent":USER_AGENT,"Cookie":cookies_header,"Referer":ORIGIN}, timeout=TIMEOUT).text
                # search for #EXT-X-MEDIA:TYPE=AUDIO lines
                m = re.search(r'LANGUAGE="?([a-zA-Z0-9\-_]+)"?', txt)
                if m:
                    return m.group(1)
                # search for audio filenames containing 'hin', 'tel', 'tam', 'eng'
                if re.search(r'\bhin\b', txt, re.I): return "Hindi"
                if re.search(r'\btel\b', txt, re.I): return "Telugu"
                if re.search(r'\btam\b', txt, re.I): return "Tamil"
                if re.search(r'\beng\b', txt, re.I): return "English"
            except Exception:
                continue
    return "Unknown"

def build_output_name(title, season, episode, audio_label, quality_label, is_movie=False):
    if is_movie:
        return f"{title}.[{audio_label}].[{quality_label}].mp4"
    else:
        s = f"S{int(season):02d}" if season is not None else ""
        e = f"E{int(episode):02d}" if episode is not None else ""
        mid = f".{s}{e}" if s or e else ""
        return f"{title}{mid}.[{audio_label}].[{quality_label}].mp4"

def run_n_m3u8dl(m3u8_url, out_path, referer, cookies_header):
    # Build the command
    save_dir = os.path.dirname(out_path)
    save_name = os.path.splitext(os.path.basename(out_path))[0]

    cmd = [
        NM3U8DL_BIN,
        m3u8_url,
        "--save-dir", save_dir,
        "--save-name", save_name,
        "--header", f"User-Agent: {USER_AGENT}",
        "--header", f"Referer: {referer}",
        "--header", f"Origin: {ORIGIN}",
        "--header", f"Cookie: {cookies_header}",
        "--select-video", "best",
        "--select-audio", "best",
        "--thread-count", "16",
        "--concurrent-download",
        "-M", "format=mp4"
    ]
    print("[*] Running:", " ".join(cmd[:8]), "...")  # don't print full cookie in logs
    try:
        p = subprocess.run(cmd, check=True)
        return p.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"[!] N_m3u8DL-RE failed: {e}")
        return False
    except FileNotFoundError:
        print(f"[!] {NM3U8DL_BIN} not found. Put it in PATH or edit NM3U8DL_BIN in script.")
        return False

def extract_season_episode_from_html(html):
    # Try JSON-LD first
    data = extract_metadata_from_jsonld(html)
    if data and data.get('@type') == 'Episode':
        s_info = data.get('partOfSeason')
        s = s_info.get('seasonNumber') if s_info else None
        e = data.get('episodeNumber')
        if s is not None and e is not None:
            return int(s), int(e)

    # Try to extract season/episode numeric info from metadata JSON
    # Look for "season":1,"episode":2 or similar
    m = re.search(r'"season"\s*:\s*(\d+)', html)
    s = int(m.group(1)) if m else None
    m2 = re.search(r'"episode"\s*:\s*(\d+)', html)
    e = int(m2.group(1)) if m2 else None
    # fallback: try pattern S01 E02 in strings
    m3 = re.search(r'[sS](\d{1,2})[ ._-]?[eE](\d{1,2})', html)
    if not m and m3:
        s = int(m3.group(1))
        e = int(m3.group(2))
    return s, e

def main():
    if len(sys.argv) < 3:
        print("Usage: python mx_auto_downloader.py cookies.txt <mx_url1> [<mx_url2> ...]")
        print("       or: python mx_auto_downloader.py cookies.txt --urls-file urls.txt")
        sys.exit(1)

    cookies_file = sys.argv[1]
    if not os.path.exists(cookies_file):
        print("cookies.txt not found:", cookies_file); sys.exit(1)

    # Build cookie header
    cookie_header = read_cookies_netscape(cookies_file)
    if not cookie_header:
        print("[!] Warning: cookie header empty. Login-protected content may fail.")

    # gather URLs
    urls = []
    if sys.argv[2] == "--urls-file" and len(sys.argv) >= 4:
        filep = sys.argv[3]
        with open(filep, "r", encoding="utf-8") as f:
            for line in f:
                u=line.strip()
                if u: urls.append(u)
    else:
        urls = sys.argv[2:]

    OUTDIR = f"mx_downloads_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(OUTDIR, exist_ok=True)
    print("[*] Output dir:", OUTDIR)

    for url in urls:
        print("\n" + "="*60)
        print("[*] Processing root URL:", url)
        page_html = fetch(url, cookie_header, referer=url)
        if not page_html:
            print("[!] Failed to fetch root URL. Skipping.")
            continue

        # Determine whether it's an episode/movie page or season page
        episode_pages = []
        if re.search(r'/detail/(?:episode|movie)/', url):
            episode_pages = [url.split("?")[0]]
        else:
            eps = gather_episode_links_from_html(page_html)
            if eps:
                episode_pages = eps
            else:
                # maybe the page itself contains a single playable item: treat root as episode
                episode_pages = [url.split("?")[0]]

        print(f"[*] Found {len(episode_pages)} episode/movie pages to try.")

        for ep_url in episode_pages:
            print("\n[>] Episode page:", ep_url)
            ep_html = fetch(ep_url, cookie_header, referer=url)
            if not ep_html:
                print("[!] Failed to fetch episode page, skipping.")
                continue

            title = extract_title(ep_html) or "Unknown.Title"
            season_num, episode_num = extract_season_episode_from_html(ep_html)

            # find m3u8 via heuristics
            m3u8 = find_m3u8_in_text(ep_html)
            if not m3u8:
                # try to find API endpoints referenced by JS
                m_api = re.search(r'(https?://[^"\']+(?:player|video|content|media)[^"\']+)', ep_html)
                if m_api:
                    api_url = m_api.group(1)
                    print("[*] Trying API endpoint:", api_url)
                    api_text = fetch(api_url, cookie_header, referer=ep_url)
                    m3u8 = find_m3u8_in_text(api_text)
            if not m3u8:
                # Try looking for JSON blob containing 'm3u8'
                json_blob = None
                mjs = re.search(r'(\{.+?"m3u8".+?\})', ep_html)
                if mjs:
                    json_blob = mjs.group(1)
                    m3u8 = find_m3u8_in_text(json_blob)
            if not m3u8:
                print("[!] No non-DRM m3u8 found (likely DRM-protected). Skipping:", title)
                continue

            # normalize m3u8 url if escaped
            m3u8 = m3u8.replace("\\/", "/")

            print("[*] Found m3u8:", m3u8)

            # fetch master playlist (if remote)
            try:
                m3u8_resp = requests.get(m3u8, headers={"User-Agent":USER_AGENT,"Cookie":cookie_header,"Referer":ep_url}, timeout=TIMEOUT)
                m3u8_resp.raise_for_status()
                m3u8_text = m3u8_resp.text
            except Exception as e:
                print(f"[!] Failed to fetch m3u8 playlist: {e}")
                continue

            variants, audio_tracks = parse_master_playlist(m3u8_text)
            chosen_variant = choose_best_variant(variants) or {"uri": m3u8}
            quality_label = get_quality_label(chosen_variant)
            audio_label = detect_audio_type(variants, audio_tracks, m3u8, cookie_header)

            is_movie = "/movie/" in ep_url
            outname = build_output_name(title, season_num, episode_num, audio_label, quality_label, is_movie=is_movie)
            outpath = os.path.join(OUTDIR, outname)
            print(f"[*] Download target: {outpath}")

            success = run_n_m3u8dl(m3u8, outpath, referer=ep_url, cookies_header=cookie_header)
            if success:
                print("[+] Finished:", outpath)
            else:
                print("[!] Failed to download:", title)

    print("\n[*] All done. Check folder:", OUTDIR)

if __name__ == "__main__":
    main()
