"""
Geohashing Calculations

Mirrors the logic in gh/model/Hash.php, Dow.php, and GlobalHash.php from https://github.com/Eupeodes/gh.
"""

import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path

import requests

# Load configuration from geohash_config.json
CONFIG_PATH = Path(__file__).parent.parent / "config" / "geohash_config.json"
with open(CONFIG_PATH) as f:
    config = json.load(f)

HOME_LAT = config["home_lat"]
HOME_LON = config["home_lon"]
W30_RULE_START = date.fromisoformat(config["w30_rule_start"])
DOW_URL = config["dow_url"]
DECIMALS = config["decimals"]
DISTANCE_KM = config["distance_km"]
MANUAL_DATE = (
    date.fromisoformat(config["manual_date"]) if config["manual_date"] else None
)
GOOGLE_MAPS_API_KEY = config.get("google_maps_api_key", "")


def hex2dec(hex16: str) -> float:
    """Mirrors Hash.php hex2dec(): converts a 16-char hex string to a float in [0, 1)."""
    o = 0.0
    for i, ch in enumerate(hex16):
        o += int(ch, 16) * (16 ** (-i - 1))
    return o


class Dow:
    """Mirrors model/Dow.php – fetches the DJIA opening from geo.crox.net."""

    @staticmethod
    def get(target_date: date) -> str:
        url = DOW_URL.format(
            year=target_date.year,
            month=target_date.month,
            day=target_date.day,
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.text.strip()


class Hash:
    """Mirrors model/Hash.php constructor."""

    def __init__(
        self,
        target_date: date,
        dow: str,
        global_hash: bool = False,
        graticule_lat: int | None = None,
        graticule_lng: int | None = None,
    ):
        date_str = target_date.strftime("%Y-%m-%d")
        md5 = hashlib.md5(f"{date_str}-{dow}".encode()).hexdigest()
        lat_hex, lng_hex = md5[:16], md5[16:32]

        lat_frac = hex2dec(lat_hex)
        lng_frac = hex2dec(lng_hex)

        if global_hash:
            self.lat = round(lat_frac * 180 - 90, DECIMALS)
            self.lng = round(lng_frac * 360 - 180, DECIMALS)
        else:
            # PHP view layer uses string concatenation, not arithmetic addition.
            # e.g. graticule -75 with fraction 0.73564 → "-75" + ".73564" = -75.73564
            # Arithmetic (-75 + 0.73564 = -74.26) gives the wrong result for negatives.
            base_lat = int(HOME_LAT) if graticule_lat is None else graticule_lat
            base_lng = int(HOME_LON) if graticule_lng is None else graticule_lng
            self.lat = self._concat(base_lat, lat_frac)
            self.lng = self._concat(base_lng, lng_frac)

    @staticmethod
    def _concat(graticule: int, frac: float) -> float:
        """Mirrors PHP: str(graticule) + substr(str(frac), 1) → float."""
        frac_str = f"{frac:.{DECIMALS}f}"[1:]  # e.g. ".73564"
        return float(f"{graticule}{frac_str}")

    def __repr__(self):
        return f"Hash(lat={self.lat}, lng={self.lng})"


def prev_trading_day(d: date) -> date:
    """Return the previous trading day."""
    d -= timedelta(days=1)
    while d.weekday() >= 5:  # 5=Saturday, 6=Sunday
        d -= timedelta(days=1)
    return d


def dow_date_for(target_date: date, lon: float) -> date:
    """
    Return the date whose DOW opening to use, applying the W30 rule.

    PHP doCalc():
      west output (lon < -30)  → uses $dow          = same-day DJIA
      east output (lon >= -30) → uses $dowDayBefore = previous trading day DJIA

    So only locations east of 30°W need the previous trading day.
    Locations west of 30°W (e.g. North America) use the same-day DJIA.
    """
    if target_date >= W30_RULE_START and lon >= -30:
        return prev_trading_day(target_date)
    return target_date


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two locations in kilometers."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _seconds_to_text(seconds: int) -> str:
    """Convert a duration in seconds to a human-readable string."""
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours} hour{'s' if hours != 1 else ''} {minutes} min{'s' if minutes != 1 else ''}"
    return f"{minutes} min{'s' if minutes != 1 else ''}"


def get_driving_time(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    api_key: str = GOOGLE_MAPS_API_KEY,
) -> dict | None:
    """
    Call the Google Maps Routes API and return driving duration.

    Returns a dict with keys:
      - "duration_text": human-readable string (e.g. "1 hour 23 mins")
      - "duration_seconds": integer seconds
      - "distance_text": human-readable distance (e.g. "95.4 km")
      - "distance_meters": integer metres
    Returns None if the API key is missing or the request fails.
    """
    if not api_key:
        return None

    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
    }
    body = {
        "origin": {
            "location": {"latLng": {"latitude": origin_lat, "longitude": origin_lon}}
        },
        "destination": {
            "location": {"latLng": {"latitude": dest_lat, "longitude": dest_lon}}
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    resp = requests.post(url, json=body, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    try:
        route = data["routes"][0]
        # Routes API returns duration as e.g. "4972s"
        duration_seconds = int(route["duration"].rstrip("s"))
        distance_meters = route["distanceMeters"]
        distance_km = distance_meters / 1000
        distance_text = f"{distance_km:.1f} km"
        return {
            "duration_text": _seconds_to_text(duration_seconds),
            "duration_seconds": duration_seconds,
            "distance_text": distance_text,
            "distance_meters": distance_meters,
        }
    except (KeyError, IndexError, ValueError):
        return None


def surrounding_graticules(lat: float, lon: float):
    """Return the 8 neighboring integer graticules around the home graticule."""
    lat_i, lon_i = int(lat), int(lon)
    out = []
    for dlat in (-1, 0, 1):
        for dlon in (-1, 0, 1):
            if dlat == 0 and dlon == 0:
                continue
            out.append((lat_i + dlat, lon_i + dlon))
    return out


def get_today_hashes(home_lat: float = HOME_LAT, home_lon: float = HOME_LON):
    """Return today's geohashing calculation results."""
    today = MANUAL_DATE if MANUAL_DATE is not None else date.today()

    dow_day = dow_date_for(today, home_lon)
    dow = Dow.get(dow_day)

    graticule = Hash(today, dow, global_hash=False)
    global_ = Hash(today, dow, global_hash=True)

    candidates = []
    for g_lat, g_lon in surrounding_graticules(home_lat, home_lon):
        neighbor_hash = Hash(
            today,
            dow,
            global_hash=False,
            graticule_lat=g_lat,
            graticule_lng=g_lon,
        )
        distance_km = haversine_km(
            home_lat, home_lon, neighbor_hash.lat, neighbor_hash.lng
        )
        candidates.append(
            {
                "graticule": {"lat": g_lat, "lng": g_lon},
                "hash": {"lat": neighbor_hash.lat, "lng": neighbor_hash.lng},
                "distance_km": round(distance_km, 3),
            }
        )

    closest_surrounding = min(candidates, key=lambda c: c["distance_km"])

    home_distance_km = haversine_km(home_lat, home_lon, graticule.lat, graticule.lng)
    home_candidate = {
        "graticule": {"lat": int(home_lat), "lng": int(home_lon)},
        "hash": {"lat": graticule.lat, "lng": graticule.lng},
        "distance_km": round(home_distance_km, 3),
    }

    closest_hash = min([home_candidate, *candidates], key=lambda c: c["distance_km"])
    within_distance = closest_hash["distance_km"] <= DISTANCE_KM

    maps_destination_url = (
        "https://www.google.com/maps/dir/?api=1&destination="
        f"{closest_hash['hash']['lat']},{closest_hash['hash']['lng']}"
    )

    driving = get_driving_time(
        home_lat,
        home_lon,
        closest_hash["hash"]["lat"],
        closest_hash["hash"]["lng"],
    )

    return {
        "date": today.isoformat(),
        "dow_date": dow_day.isoformat(),
        "djia": dow,
        "graticule": {"lat": graticule.lat, "lng": graticule.lng},
        "global": {"lat": global_.lat, "lng": global_.lng},
        "closest_hash": closest_hash,
        "closest_surrounding": closest_surrounding,
        "maps_destination_url": maps_destination_url,
        "within_distance": within_distance,
        "distance": closest_hash["distance_km"],
        "driving": driving,
    }


if __name__ == "__main__":
    today = MANUAL_DATE if MANUAL_DATE is not None else date.today()
    dow_day = dow_date_for(today, HOME_LON)
    dow = Dow.get(dow_day)
    md5_input = f"{today.strftime('%Y-%m-%d')}-{dow}"
    md5_hex = hashlib.md5(md5_input.encode()).hexdigest()
    lat_frac = hex2dec(md5_hex[:16])
    lng_frac = hex2dec(md5_hex[16:32])

    print(f"--- DEBUG ---")
    print(f"Target date : {today}")
    print(f"DOW date    : {dow_day}")
    print(f"DJIA raw    : {repr(dow)}")
    print(f"MD5 input   : {repr(md5_input)}")
    print(f"MD5 hex     : {md5_hex}")
    print(f"lat_frac    : {lat_frac}")
    print(f"lng_frac    : {lng_frac}")
    print(f"int(HOME_LAT) = {int(HOME_LAT)}, int(HOME_LON) = {int(HOME_LON)}")

    print(f"--- OUTPUT ---")
    result = get_today_hashes()
    print(f"Date       : {result['date']}")
    print(f"DOW date   : {result['dow_date']}")
    print(f"DJIA open  : {result['djia']}")
    print(f"Graticule  : {result['graticule']['lat']}, {result['graticule']['lng']}")
    print(f"Global     : {result['global']['lat']}, {result['global']['lng']}")
    print(
        "Closest 9  : "
        f"{result['closest_hash']['hash']['lat']}, "
        f"{result['closest_hash']['hash']['lng']} "
        f"(grid {result['closest_hash']['graticule']['lat']},"
        f"{result['closest_hash']['graticule']['lng']} | "
        f"{result['closest_hash']['distance_km']} km)"
    )
    print(
        "Closest 8  : "
        f"{result['closest_surrounding']['hash']['lat']}, "
        f"{result['closest_surrounding']['hash']['lng']} "
        f"(grid {result['closest_surrounding']['graticule']['lat']},"
        f"{result['closest_surrounding']['graticule']['lng']} | "
        f"{result['closest_surrounding']['distance_km']} km)"
    )
    print(f"Distance   : {result['distance']} km")
    print(f"Within {DISTANCE_KM} km: {result['within_distance']}")
    if result["driving"]:
        print(
            f"Drive      : {result['driving']['duration_text']} ({result['driving']['distance_text']})"
        )
    else:
        print("Drive      : (no API key configured)")
