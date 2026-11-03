#!/usr/bin/env python3
"""Bursa mekanlarini OpenStreetMap'ten (Overpass) cekip places-bursa.json dosyasina yazar.
Elle eklenen mekanlar (id'si n/w/r ile baslamayan), etkinlikler ve yorumlar korunur."""
import json, os, sys, time, datetime, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'places-bursa.json')
# Bursa'nin tum ilceleri
DISTRICTS = ['Nilüfer', 'Osmangazi', 'Yıldırım', 'Mudanya', 'Gemlik', 'İnegöl', 'Mustafakemalpaşa', 'Karacabey', 'Orhangazi',
             'İznik', 'Gürsu', 'Kestel', 'Yenişehir', 'Orhaneli', 'Keles', 'Büyükorhan', 'Harmancık']
ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter',
             'https://overpass.private.coffee/api/interpreter', 'https://z.overpass-api.de/api/interpreter']

def query(district):
    # (area.a)(area.p): ilce sinirlari ile Bursa il siniri kesisimi (baska illerdeki ayni isimli ilceler karismaz)
    return ('[out:json][timeout:180];'
            'area["boundary"="administrative"]["admin_level"="4"]["name"="Bursa"]->.p;'
            'area["boundary"="administrative"]["admin_level"="6"]["name"="%s"]->.a;'
            '(nwr["amenity"~"^(cafe|restaurant)$"]["name"](area.a)(area.p);'
            'nwr["leisure"="park"]["name"](area.a)(area.p);'
            'nwr["tourism"~"^(museum|gallery|attraction)$"]["name"](area.a)(area.p););'
            'out center tags;') % district

def fetch(q):
    data = urllib.parse.urlencode({'data': q}).encode()
    last = None
    for attempt in range(4):
        for ep in ENDPOINTS:
            try:
                req = urllib.request.Request(ep, data=data, headers={'User-Agent': 'around-app-places/1.0'})
                with urllib.request.urlopen(req, timeout=200) as r:
                    return json.load(r)
            except Exception as e:
                last = e
        time.sleep(5 * (attempt + 1))
    raise RuntimeError('Overpass yanit vermedi: %s' % last)

def cat_of(t):
    a, l, tu = t.get('amenity'), t.get('leisure'), t.get('tourism')
    if a == 'cafe': return 'cafe'
    if a == 'restaurant': return 'food'
    if l == 'park': return 'park'
    if tu in ('museum', 'gallery', 'attraction'): return 'activity'
    return None

def convert(elements, district):
    out = []
    for el in elements:
        t = el.get('tags') or {}
        name = (t.get('name') or '').strip()
        cat = cat_of(t)
        if not name or not cat: continue
        lat = el.get('lat') if el.get('lat') is not None else (el.get('center') or {}).get('lat')
        lon = el.get('lon') if el.get('lon') is not None else (el.get('center') or {}).get('lon')
        if lat is None or lon is None: continue
        p = {'id': el['type'][0] + str(el['id']), 'name': name, 'cat': cat, 'district': district,
             'area': t.get('addr:suburb') or t.get('addr:neighbourhood') or '',
             'lat': round(lat, 6), 'lon': round(lon, 6)}
        if t.get('opening_hours'): p['hours'] = t['opening_hours']
        ia = t.get('internet_access')
        if ia in ('wlan', 'wifi', 'yes'): p['wifi'] = 1
        elif ia == 'no': p['wifi'] = 0
        if t.get('smoking') == 'no': p['nosmoke'] = True
        elif t.get('smoking') == 'yes': p['nosmoke'] = False
        if t.get('dog') == 'yes': p['pet'] = True
        elif t.get('dog') == 'no': p['pet'] = False
        if t.get('wheelchair') == 'yes': p['access'] = True
        elif t.get('wheelchair') == 'no': p['access'] = False
        if t.get('bbq') == 'yes': p['bbq'] = True
        elif t.get('bbq') == 'no': p['bbq'] = False
        out.append(p)
    return out

def main():
    old = {}
    if os.path.exists(OUT):
        try: old = json.load(open(OUT, encoding='utf-8'))
        except Exception: old = {}
    places, seen = [], set()
    for d in DISTRICTS:
        res = fetch(query(d))
        for p in convert(res.get('elements', []), d):
            key = (p['name'].lower(), round(p['lat'], 3), round(p['lon'], 3))
            if key in seen: continue
            seen.add(key); places.append(p)
        print(d, 'tamam', file=sys.stderr)
        time.sleep(3)
    if len(places) < 50:
        sys.exit('Cok az mekan geldi (%d), dosya degistirilmedi.' % len(places))
    manual = [p for p in old.get('places', []) if str(p.get('id', ''))[:1] not in ('n', 'w', 'r')]
    by_id = {p['id']: p for p in places}
    for p in manual: by_id[p['id']] = p
    # eski dosyada elle girilmis priz/wifi/ses gibi bilgiler varsa OSM kaydina eklenir
    for p in old.get('places', []):
        q = by_id.get(p.get('id'))
        if q and str(p['id'])[:1] in ('n', 'w', 'r'):
            for k in ('plug', 'wifi', 'noise', 'desk', 'group', 'price', 'note', 'nosmoke', 'pet', 'access', 'bbq'):
                if k in p and p[k] is not None: q[k] = p[k]
    counts = {}
    for p in by_id.values(): counts[p['district']] = counts.get(p['district'], 0) + 1
    districts = sorted(counts, key=lambda d: -counts[d])
    result = {'city': 'Bursa', 'districts': districts, 'source': 'OpenStreetMap',
              'updated': datetime.date.today().isoformat(),
              'places': sorted(by_id.values(), key=lambda x: (x['district'], x['name'])),
              'events': old.get('events', []), 'reviews': old.get('reviews', {})}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, separators=(',', ':'))
    print('Yazildi:', len(result['places']), 'mekan', file=sys.stderr)

if __name__ == '__main__':
    main()
