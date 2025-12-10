
import mx
import os
import json
import re

def test():
    eid = "10bd65400ec90976ebfcbcb739bf7543"
    url = f"https://www.mxplayer.in/detail/episode/{eid}"

    referer = "https://www.mxplayer.in/"
    cookie = ""

    print(f"Fetching {url}")
    resp = mx.fetch(url, cookie, referer)
    if resp:
        # Search for episode IDs
        links = re.findall(r'detail/episode/([0-9a-f]{32})', resp)
        unique = set(links)
        print(f"Found {len(unique)} unique episode IDs: {unique}")

        # Check for 'next' field
        if '"next":' in resp:
            print("Found 'next' field")

        # Dump sectionsData part if found
        m = re.search(r'"sectionsData":(\{.+?\})', resp)
        if m:
            print("Found sectionsData JSON block")
            try:
                data = json.loads(m.group(1))
                # Traverse to find episodes
                # Usually sectionsData -> ID -> tabs -> containers -> episodes?
                print(json.dumps(data, indent=2)[:2000])
            except:
                print("Failed to parse sectionsData")
    else:
        print("Failed to fetch.")

if __name__ == '__main__':
    test()
