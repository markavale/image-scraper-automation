from helpers.base_scraper import Scraper
from core.scraper_strategy import SearchScraperStrategy
from core.photo_collector import PhotoCollector
from core.photo_manager import PhotoManager
from core.dewatermarker import Dewatermarker
import json
import argparse
from typing import List
import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

# Setup basic logging (if not already configured elsewhere)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure detailed logger function
def setup_detailed_logger(name):
    """
    Set up a logger with both console (INFO) and file (DEBUG) handlers.
    
    Args:
        name: Name of the logger
    
    Returns:
        A configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger
        
    try:
        # Create logs directory if it doesn't exist yet
        os.makedirs('logs', exist_ok=True)
        
        # Add rotating file handler for DEBUG and above
        file_handler = RotatingFileHandler(
            'logs/debug.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Add a separate error log file for WARNING and above
        error_file_handler = RotatingFileHandler(
            'logs/error.log',
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_file_handler.setLevel(logging.WARNING)
        error_file_handler.setFormatter(file_formatter)
        logger.addHandler(error_file_handler)
        
    except (PermissionError, IOError) as e:
        # Log to console if file logging fails
        print(f"Warning: Could not set up file logging due to: {str(e)}")
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

class PhotoProcessor:
    def __init__(self, bib_numbers: List[str]):
        self.bib_numbers = bib_numbers
        self.scraper = Scraper()
        self.collector = PhotoCollector(self.scraper)
        self.photo_manager = PhotoManager()
        self.dewatermarker = Dewatermarker()
        # Set up the detailed logger for this class
        self.logger = setup_detailed_logger('PhotoProcessor')

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
        self.logger.info(f"Starting processing for keyword: '{keyword}' and bib numbers: {self.bib_numbers}")
        self.logger.debug(f"Process parameters: keyword='{keyword}', save_results={save_results}, use_jquery={use_jquery}")
        
        self.logger.debug("Fetching event IDs for the given keyword")
        event_ids = self.get_event_ids(keyword, use_jquery)
        self.logger.info(f"Found event IDs: {event_ids}")
        self.logger.debug(f"Detailed event IDs: {json.dumps(event_ids, indent=2)}")
        
        self.logger.debug("Generating target metadata for events and bib numbers")
        target_metadata = self.get_target_metadata(event_ids)
        self.logger.debug(f"Generated {len(target_metadata)} metadata entries")
        
        self.logger.debug("Collecting photos based on target metadata")
        photos_by_bib_number = self.collector.collect_photos(target_metadata)
        self.logger.debug(f"Collected photos structure: {json.dumps({k: len(v) for k, v in photos_by_bib_number.items()}, indent=2)}")
        
        if save_results:
            self.logger.debug("Saving raw photo metadata to res.json")
            with open("res.json", "w") as f:
                json.dump(photos_by_bib_number, f)
            self.logger.info("Raw photo metadata saved to res.json")
        
        # Download raw photos and get their paths
        self.logger.debug("Starting photo download process")
        raw_image_paths = self.photo_manager.download_photos(photos_by_bib_number)
        self.logger.info(f"Downloaded {len(raw_image_paths)} raw images.")
        for i, path in enumerate(raw_image_paths[:10]):  # Log first 10 to avoid verbose output
            self.logger.debug(f"Downloaded image {i+1}: {path}")
        if len(raw_image_paths) > 10:
            self.logger.debug(f"... and {len(raw_image_paths)-10} more images")

        # Dewatermark the downloaded images
        if raw_image_paths:
            self.logger.info("Starting dewatermarking process...")
            self.logger.debug(f"Passing {len(raw_image_paths)} images to dewatermarker")
            self.logger.debug(f"Dewatermarker configuration: max_requests_before_rotation={self.dewatermarker.max_requests_before_rotation}")
            
            processed_image_paths = asyncio.run(self.dewatermarker.process_images(raw_image_paths))
            
            self.logger.info(f"Finished dewatermarking. Processed {len(processed_image_paths)} images.")
            for i, path in enumerate(processed_image_paths[:10]):  # Log first 10 to avoid verbose output
                self.logger.debug(f"Processed image {i+1}: {path}")
            if len(processed_image_paths) > 10:
                self.logger.debug(f"... and {len(processed_image_paths)-10} more images")
        else:
            self.logger.warning("No raw images were downloaded, skipping dewatermarking.")

        # Return the original metadata (or modify if needed)
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
    
    # Set up detailed logging for main function
    main_logger = setup_detailed_logger('main')
    main_logger.debug("Creating PhotoProcessor instance")
    processor = PhotoProcessor(bib_numbers=bib_numbers)
    main_logger.debug(f"Starting process with keyword={args.keyword}, use_jquery={args.use_jquery}")
    processor.process(keyword=args.keyword, use_jquery=args.use_jquery, save_results=args.save_results)
    main_logger.info("Processing finished.")
if __name__ == '__main__':
    main()