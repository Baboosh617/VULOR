from django.core.cache import cache

PRODUCTS_CACHE_VERSION_KEY = 'products_cache_version'


def get_products_cache_version():
    version = cache.get(PRODUCTS_CACHE_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(PRODUCTS_CACHE_VERSION_KEY, version, None)
    return version


def bump_products_cache_version():
    """Call after any Product create/update/delete to invalidate all cached product pages at once."""
    try:
        cache.incr(PRODUCTS_CACHE_VERSION_KEY)
    except ValueError:
        cache.set(PRODUCTS_CACHE_VERSION_KEY, 2, None)