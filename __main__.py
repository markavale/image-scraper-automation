from helpers.base_scraper import Scraper
from core.scraper_strategy import SearchScraperStrategy
from core.photo_collector import PhotoCollector
from core.photo_manager import PhotoManager
import json
import argparse
from typing import List

class PhotoProcessor:
    def __init__(self, bib_numbers: List[str]):
        self.bib_numbers = bib_numbers
        self.scraper = Scraper()
        self.collector = PhotoCollector(self.scraper)
        self.photo_manager = PhotoManager()

    def get_event_ids(self, keyword: str, use_jquery: bool = False) -> List[str]:
        search_scraper = SearchScraperStrategy(keyword, use_jquery)
        return search_scraper.events

    def get_target_metadata(self, event_ids: List[str]) -> List[dict]:
        target_metadata = []
        for event_id in event_ids:
            for bib_number in self.bib_numbers:
                target_metadata.append({
                    "event_id": event_id,
                    "bib_number": bib_number,
                    "page_number": 1,
                    "target_link": f"https://geosnapshot.com/api/v1/events/{event_id}/photos?page=1&photo_text={bib_number}&user_id=445617"
                })
        return target_metadata

    def process(self, keyword: str, save_results: bool = True, use_jquery: bool = False) -> dict:
        event_ids = self.get_event_ids(keyword, use_jquery)
        print(event_ids)
        target_metadata = self.get_target_metadata(event_ids)
        
        photos_by_bib_number = self.collector.collect_photos(target_metadata)
        
        if save_results:
            with open("res.json", "w") as f:
                json.dump(photos_by_bib_number, f)
        
        self.photo_manager.download_photos(photos_by_bib_number)
        return photos_by_bib_number

def main():
    # Create argument parser
    parser = argparse.ArgumentParser(description='Process photos based on bib numbers and keywords')
    parser.add_argument('--bib_numbers', type=str, required=True, 
                        help='Comma-separated list of bib numbers (e.g., "11653,12345")')
    parser.add_argument('--keyword', type=str, required=True,
                        help='Keyword to search for events')
    parser.add_argument('--use_jquery', action='store_true', default=False,
                        help='Use jQuery for scraping (default: False)')
    parser.add_argument('--save_results', action='store_true', default=True,
                        help='Save results to file (default: True)')
    
    args = parser.parse_args()
    
    # Split the comma-separated bib numbers into a list
    bib_numbers = [bib.strip() for bib in args.bib_numbers.split(',')]
    
    processor = PhotoProcessor(bib_numbers=bib_numbers)
    processor.process(keyword=args.keyword, use_jquery=args.use_jquery, save_results=args.save_results)

if __name__ == '__main__':
    main()