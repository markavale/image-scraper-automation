from typing import Dict, List
from helpers.base_scraper import Scraper

class PhotoCollector:
    def __init__(self, scraper: Scraper):
        self.scraper = scraper
        self.base_url = "https://geosnapshot.com/api/v1/events"

    def _build_url(self, event_id: str, page: int, bib_number: str) -> str:
        return f"{self.base_url}/{event_id}/photos?page={page}&photo_text={bib_number}&user_id=445617"
    
# https://geosnapshot.com/api/v1/events/33519/albums/83134/photos?page=1&photo_text=11652

    def collect_photos(self, target_metadatas: List[Dict]) -> Dict[str, List[str]]:
        photos_by_bib_number: Dict[str, List[str]] = {}

        for metadata in target_metadatas:
            bib_number = metadata["bib_number"]
            if bib_number not in photos_by_bib_number:
                photos_by_bib_number[bib_number] = []

            url = metadata["target_link"]
            while url:
                response = self.scraper._request(method="GET", url=url)
                if response.status_code != 200:
                    break
                else:
                    res_payload = response.json()
                    
                    photos_by_bib_number[bib_number].extend(
                        photo['zoomImg'] for photo in res_payload.get('photos', [])
                        if 'zoomImg' in photo
                    )
                    
                    next_page = res_payload.get('meta', {}).get('nextPage')
                    url = self._build_url(metadata['event_id'], next_page, bib_number) if next_page else None

        return photos_by_bib_number 