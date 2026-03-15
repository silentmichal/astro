from http.server import BaseHTTPRequestHandler
import json
import swisseph as swe
from datetime import datetime
from timezonefinder import TimezoneFinder
import pytz

SIGNS      = ["Baran","Byk","Bliźnięta","Rak","Lew","Panna","Waga","Skorpion","Strzelec","Koziorożec","Wodnik","Ryby"]
SIGN_SYM   = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]
ELEMENTS   = ["fire","fire","air","water","fire","earth","air","water","fire","earth","air","water"]
ELEM_NAMES = ["Ogień","Ogień","Powietrze","Woda","Ogień","Ziemia","Powietrze","Woda","Ogień","Ziemia","Powietrze","Woda"]

PLANET_IDS = {
    'sun':swe.SUN,'moon':swe.MOON,'mercury':swe.MERCURY,'venus':swe.VENUS,
    'mars':swe.MARS,'jupiter':swe.JUPITER,'saturn':swe.SATURN,
    'uranus':swe.URANUS,'neptune':swe.NEPTUNE,'pluto':swe.PLUTO,
}

def lon_to_sign(lon):
    lon = float(lon) % 360.0
    idx = int(lon / 30)
    pos = lon % 30.0
    return {
        'sign': SIGNS[idx], 'sym': SIGN_SYM[idx],
        'element': ELEMENTS[idx], 'elementName': ELEM_NAMES[idx],
        'deg': int(pos), 'min': int((pos % 1) * 60),
        'raw': round(lon, 4), 'idx': idx, 'house': None,
    }

def placidus_house(planet_lon, cusps):
    # cusps is 0-indexed (len=12): cusps[0]=house1, cusps[11]=house12
    p = float(planet_lon) % 360.0
    for i in range(12):
        c1 = float(cusps[i]) % 360.0
        c2 = float(cusps[(i + 1) % 12]) % 360.0
        if c1 < c2:
            if c1 <= p < c2:
                return i + 1
        else:  # cusp crosses 0°/360°
            if p >= c1 or p < c2:
                return i + 1
    return 1

def calculate_chart(date_str, time_str, lat, lon):
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon) or 'UTC'

    year, month, day = map(int, date_str.split('-'))
    hour, minute     = map(int, time_str.split(':'))

    tz = pytz.timezone(tz_name)
    # is_dst=False avoids AmbiguousTimeError during DST transitions
    local_dt = tz.localize(datetime(year, month, day, hour, minute), is_dst=False)
    utc_dt   = local_dt.astimezone(pytz.utc)
    ut_hour  = utc_dt.hour + utc_dt.minute / 60.0

    jd    = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, ut_hour)
    flags = swe.FLG_MOSEPH | swe.FLG_SPEED

    # Planets
    planets = {}
    for name, pid in PLANET_IDS.items():
        xx, _ = swe.calc_ut(jd, pid, flags)
        planets[name] = lon_to_sign(xx[0])

    # Mean North Node
    xx_node, _ = swe.calc_ut(jd, swe.MEAN_NODE, flags)
    node = lon_to_sign(xx_node[0])

    # Placidus houses — cusps is len=12 (0-indexed)
    cusps, ascmc = swe.houses(jd, lat, lon, b'P')
    asc = lon_to_sign(ascmc[0])
    mc  = lon_to_sign(ascmc[1])

    for name in PLANET_IDS:
        planets[name]['house'] = placidus_house(planets[name]['raw'], cusps)

    planets['asc']  = asc
    planets['mc']   = mc
    planets['node'] = node

    return {
        'planets':    planets,
        'asc':        asc,
        'mc':         mc,
        'node':       node,
        'house_cusps':[round(float(c), 4) for c in cusps],
        'jd':         round(jd, 6),
        'timezone':   tz_name,
        'utc_offset': round(local_dt.utcoffset().total_seconds() / 3600, 1),
    }


class handler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length))
            result = calculate_chart(
                body['date'], body['time'],
                float(body['lat']), float(body['lon'])
            )
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as e:
            import traceback
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': str(e),
                'trace': traceback.format_exc()
            }).encode())

    def log_message(self, fmt, *args):
        pass
