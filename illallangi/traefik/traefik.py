from yarl import URL

from .routecollection import RouteCollection


class Traefik(object):
    def __init__(self, url, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = URL(url) if not isinstance(url, URL) else url

    def __repr__(self):
        return f'{self.__class__}({self.url})'

    def __str__(self):
        return f'{self.url}'

    @property
    def routes(self):
        return RouteCollection(self)
