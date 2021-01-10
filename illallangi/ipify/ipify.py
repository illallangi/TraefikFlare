from ipaddress import ip_address

from requests import get as http_get

from yarl import URL


class IPIFY(object):
    def __init__(self, url, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = URL(url) if not isinstance(url, URL) else url

    def __repr__(self):
        return f"{self.__class__}({self.url})"

    def __str__(self):
        return f"{self.url}"

    @property
    def ip_address(self):
        return ip_address(http_get(self.url).text)
