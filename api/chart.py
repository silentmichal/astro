from http.server import BaseHTTPRequestHandler
import json
import swisseph as swe
from datetime import datetime
from timezonefinder import TimezoneFinder
import pytz

# ── Sign data ──────────────────────────────────────────────────────────────
SIGNS = ["Baran","Byk","Bliźnięta","Rak","Lew","Panna",
         "Waga","Skorpion","Strzelec","Koziorożec","Wodnik","Ryby"]
SIGN_SYM = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]
ELEMENTS = ["fire","fire","air","water","fire","earth",
            "air","water","fire","earth","air","water"]
ELEMENT_NAMES = ["Ogień","Ogień","Powietrze","Woda","Ogień","Ziemia",
                 "Powietrze","Woda","Ogień","Ziemia","Powietrze","Woda"]

# ── Planet IDs ─────────────────────────────────────────────────────────────
PLANET_IDS = {
    'sun':     swe.SUN,
    'moon':    swe.MOON,
    'mercury': swe.MERCURY,
    'venus':   swe.VENUS,
    'mars':    swe.MARS,
    'jupiter': swe.JUPITER,
    'saturn':  swe.SATURN,
    'uranus':  swe.URANUS,
    'neptune': swe.NEPTUNE,
    'pluto':   swe.PLUTO,
}

def lon_to_sign(lon):
    """Convert ecliptic longitude to sign data dict."""
    lon = lon % 360
    idx = int(lon / 30)
    pos = lon % 30
    return {
        'sign': SIGNS[idx],
        'sym':  SIGN_SYM[idx],
        'element': ELEMENTS[idx],
        'elementName': ELEMENT_NAMES[idx],
        'deg': int(pos),
        'min': int((pos % 1) * 60),
        'raw': round(lon, 4),
        'idx': idx,
    }

def get_placidus_house(planet_lon, cusps):
    """
    Determine Placidus house number for a planet.
    cusps: tuple of 13 floats from swe.houses() — cusps[1..12] are the house cusps.
    """
    p = planet_lon % 360
    for i in range(1, 13):
        c_start = cusps[i] % 360
        c_end   = cusps[i % 12 + 1] % 360
        if c_start < c_end:
            if c_start <= p < c_end:
                return i
        else:  # wraps 0°/360°
            if p >= c_start or p < c_end:
                return i
    return 1

def calculate_chart(date_str, time_str, lat, lon):
    """
    Full chart calculation using Swiss Ephemeris (Moshier, no data files)
    and Placidus house system.
    date_str: 'YYYY-MM-DD'
    time_str: 'HH:MM'
    lat, lon: floats (geographic coordinates of birth place)
    Returns dict matching frontend structure.
    """
    # ── Timezone → UTC ─────────────────────────────────────────────────────
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    if not tz_name:
        tz_name = 'UTC'

    year, month, day = map(int, date_str.split('-'))
    hour, minute     = map(int, time_str.split(':'))

    tz = pytz.timezone(tz_name)
    local_dt = datetime(year, month, day, hour, minute)
    local_dt_loc = tz.localize(local_dt, is_dst=None)
    utc_dt = local_dt_loc.astimezone(pytz.utc)
    ut_hour = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0

    # ── Julian Day (UT) ─────────────────────────────────────────────────────
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, ut_hour)

    # ── Flags: Moshier ephemeris (no data files required) ──────────────────
    flags = swe.FLG_MOSEPH | swe.FLG_SPEED

    # ── Planet positions ────────────────────────────────────────────────────
    planets = {}
    for name, pid in PLANET_IDS.items():
        result, _ = swe.calc_ut(jd, pid, flags)
        planets[name] = lon_to_sign(result[0])

    # ── Mean North Node ─────────────────────────────────────────────────────
    node_result, _ = swe.calc_ut(jd, swe.MEAN_NODE, flags)
    node = lon_to_sign(node_result[0])

    # ── Placidus houses ─────────────────────────────────────────────────────
    # swe.houses() returns (cusps_13, ascmc_8)
    # cusps[1..12] = house cusps; ascmc[0] = ASC, ascmc[1] = MC
    cusps, ascmc = swe.houses(jd, lat, lon, b'P')
    asc = lon_to_sign(ascmc[0])
    mc  = lon_to_sign(ascmc[1])

    # ── Assign house numbers ────────────────────────────────────────────────
    for name in PLANET_IDS:
        planets[name]['house'] = get_placidus_house(planets[name]['raw'], cusps)
    node['house'] = None
    asc['house']  = None
    mc['house']   = None

    # Add asc/mc/node into planets dict (frontend expects them there)
    planets['asc']  = asc
    planets['mc']   = mc
    planets['node'] = node

    return {
        'planets': planets,
        'asc':  asc,
        'mc':   mc,
        'node': node,
        'house_cusps': list(cusps),
        'jd': jd,
        'timezone': tz_name,
        'utc_offset': round((local_dt_loc.utcoffset().total_seconds() / 3600), 1),
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
                date_str = body['date'],
                time_str = body['time'],
                lat      = float(body['lat']),
                lon      = float(body['lon']),
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
        pass  # suppress default logging
