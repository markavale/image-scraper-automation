from core.scraper_strategy import SearchScraperStrategy
from typing import Optional, Union, List


class GeoSnapScraper:
    def __init__(self, keyword: str, bib_number: Union[List[str], str] = None):
        self.keyword = keyword
        self.bib_number = bib_number

    def get_events(self):
        _search_events = SearchScraperStrategy(self.keyword)
        return _search_events.events

    def get_photos(self):
        _get_photos = GetPhotosScraperStrategy(self.events, self.bib_number)
        return _get_photos.photos