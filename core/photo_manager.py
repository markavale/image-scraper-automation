from typing import Dict, List
import os
import requests
from abc import ABC, abstractmethod
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PhotoDownloader(ABC):
    @abstractmethod
    def download(self, url: str, save_path: str) -> bool:
        pass

class DefaultPhotoDownloader(PhotoDownloader):
    def download(self, url: str, save_path: str) -> bool:
        response = requests.get(url)
        if response.status_code == 200:
            # Ensure the directory exists before saving
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(response.content)
            logging.info(f"Successfully downloaded image to {save_path}")
            return True
        logging.warning(f"Failed to download image from {url}. Status code: {response.status_code}")
        return False

class PhotoManager:
    def __init__(self, base_dir: str = "media", downloader: PhotoDownloader = None):
        self.raw_dir = os.path.join(base_dir, "raw")
        self.downloader = downloader or DefaultPhotoDownloader()

    def download_photos(self, photos_by_bib_number: Dict[str, List[str]]) -> List[str]:
        os.makedirs(self.raw_dir, exist_ok=True) # Ensure base raw directory exists
        downloaded_paths = []

        for bib_number, urls in photos_by_bib_number.items():
            bib_dir = os.path.join(self.raw_dir, bib_number)
            os.makedirs(bib_dir, exist_ok=True)

            for i, url in enumerate(urls):
                # Use original filename if possible, otherwise generate one
                # Basic extraction, might need improvement based on actual URL formats
                try:
                    filename = os.path.basename(url.split('?')[0])
                    if not filename or '.' not in filename: # Basic check for valid filename
                        filename = f"image_{bib_number}_{i}.jpeg"
                except Exception:
                    filename = f"image_{bib_number}_{i}.jpeg"
                
                image_path = os.path.join(bib_dir, filename) 
                if not self.downloader.download(url, image_path):
                    logging.warning(f"Skipping failed download: {url}")
                else:
                    downloaded_paths.append(image_path)
                    
        return downloaded_paths