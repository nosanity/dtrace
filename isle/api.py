import logging
from django.conf import settings
from django.core.cache import caches
from django.utils import timezone
import requests

DEFAULT_CACHE = caches['default']


class ApiError(Exception):
    pass


class Api:
    """
    класс, реализующий запрос к ручке ILE с поддержкой получения и хранения токена, а также
    его обновлением по истечении его действия
    """
    TOKEN_CACHE_KEY = 'ILE_TOKEN'
    EVENTS_DATA_CACHE_KEY = 'EVENTS_DATA'
    LAST_FETCH_CACHE_KEY = 'LAST_TIME_FETCHED'
    MAX_RETRIES = 2

    def __init__(self):
        self.token = self.get_token()

    def get_token(self):
        return DEFAULT_CACHE.get(self.TOKEN_CACHE_KEY)

    def refresh_token(self):
        try:
            r = requests.get(
                settings.ILE_GET_TOKEN_URL,
                auth=settings.ILE_TOKEN_USER,
                timeout=settings.CONNECTION_TIMEOUT,
                verify=False
            )
            assert r.ok
            DEFAULT_CACHE.set(self.TOKEN_CACHE_KEY, r.json()['token'], timeout=int(r.json()['duration']))
            self.token = r.json()['token']
            return r.json()['token']
        except AssertionError:
            logging.error('ILE returned code %s, reason: %s' % (r.status_code, r.reason))
            raise ApiError
        except requests.RequestException:
            logging.exception('ILE connection failure')
            raise ApiError
        except Exception:
            logging.exception('ILE unexpected answer: %s' % r.json())
            raise ApiError

    def get_events_data(self, force=False, retry=0):
        if not force:
            val = DEFAULT_CACHE.get(self.EVENTS_DATA_CACHE_KEY)
            fetch_dt = DEFAULT_CACHE.get(self.LAST_FETCH_CACHE_KEY)
            do_refresh = fetch_dt is None or (timezone.now() - fetch_dt).seconds < settings.API_DATA_CACHE_TIME \
                         or val is None
            if not do_refresh:
                return val, False
        try:
            r = requests.get(
                settings.ILE_EVENTS_URL,
                headers={'Authorization': 'Bearer %s' % self.token},
                timeout=settings.CONNECTION_TIMEOUT,
                verify=False
            )
            if r.status_code == 401:
                if retry < self.MAX_RETRIES:
                    return self.get_events_data(force=force, retry=retry + 1)
                else:
                    raise ApiError
            assert r.ok
            DEFAULT_CACHE.set(self.EVENTS_DATA_CACHE_KEY, r.json(), timeout=settings.API_DATA_CACHE_TIME)
            return r.json(), True
        except AssertionError:
            logging.error('ILE returned code %s, reason: %s' % (r.status_code, r.reason))
            raise ApiError
        except requests.RequestException:
            logging.exception('ILE connection failure')
            raise ApiError
