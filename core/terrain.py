from functools import lru_cache
from pathlib import Path

import srtm as _srtm_lib

from core.config import TILE_DIR

_tile_path = Path(TILE_DIR)
_tile_path.mkdir(parents=True, exist_ok=True)

_srtm = _srtm_lib.get_data(local_cache_dir=str(_tile_path))


@lru_cache(maxsize=16384)
def terrain_elev(lat_r: float, lon_r: float) -> float:
    e = _srtm.get_elevation(lat_r, lon_r)
    return float(e) if e is not None else 0.0


def compute_agl(beacon) -> float:
    return max(0.0, beacon.alt_m - terrain_elev(round(beacon.lat, 3), round(beacon.lon, 3)))
