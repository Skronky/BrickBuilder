# BrickBuilder/ldraw/network_filesystem.py
# Subclasses cuddlyogre's FileSystem — overrides locate() to fetch missing
# .dat files from the gkjohnson CDN instead of returning None.
# His filesystem.py is untouched. All changes live here.

import os
import urllib.request
import urllib.error

from ..constants      import CACHE_DIR_DAT as _CACHE_DIR
from ..inc.filesystem import FileSystem

CDN_BASE  = "https://raw.githubusercontent.com/gkjohnson/ldraw-parts-library/master/complete/ldraw"
CDN_PATHS = ["parts", "p", "p/48", "p/8", "parts/textures", "models"]


class NetworkFileSystem(FileSystem):

    @classmethod
    def locate(cls, filename):
        local = super().locate(filename)
        if local:
            return local
        cached = cls._cache_path(filename)
        if os.path.isfile(cached):
            return cached
        return cls._fetch(filename)

    @classmethod
    def _cache_path(cls, filename):
        clean = filename.replace("\\", os.sep).replace("/", os.sep).lstrip(os.sep)
        return os.path.join(_CACHE_DIR, clean)

    @classmethod
    def _fetch(cls, filename):
        clean = filename.replace("\\", "/").lstrip("/").lower()
        for cdn_dir in CDN_PATHS:
            result = cls._fetch_url(f"{CDN_BASE}/{cdn_dir}/{clean}", filename)
            if result:
                return result
        print(f"BrickBuilder: could not locate '{filename}' locally or on CDN")
        return None

    @classmethod
    def _fetch_url(cls, url, filename):
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = r.read()
                path = cls._cache_path(filename)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, 'wb').write(data)
                print(f"BrickBuilder: fetched '{filename}' from CDN")
                return path
        except urllib.error.HTTPError:
            return None
        except (urllib.error.URLError, OSError) as e:
            print(f"BrickBuilder: error fetching '{filename}': {e}")
            return None

    @classmethod
    def clear_cache(cls):
        import shutil
        if os.path.isdir(_CACHE_DIR):
            shutil.rmtree(_CACHE_DIR)
            print(f"BrickBuilder: cleared cache at {_CACHE_DIR}")
