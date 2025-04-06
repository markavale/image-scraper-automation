from typing import Dict, List
import os
import requests
from abc import ABC, abstractmethod

class PhotoDownloader(ABC):
    @abstractmethod
    def download(self, url: str, save_path: str) -> bool:
        pass

class DefaultPhotoDownloader(PhotoDownloader):
    def download(self, url: str, save_path: str) -> bool:
        response = requests.get(url)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            return True
        return False

class PhotoManager:
    def __init__(self, base_dir: str = "media", downloader: PhotoDownloader = None):
        self.base_dir = base_dir
        self.downloader = downloader or DefaultPhotoDownloader()

    def download_photos(self, photos_by_bib_number: Dict[str, List[str]]) -> None:
        os.makedirs(self.base_dir, exist_ok=True)

        for bib_number, urls in photos_by_bib_number.items():
            bib_dir = os.path.join(self.base_dir, bib_number)
            os.makedirs(bib_dir, exist_ok=True)

            for i, url in enumerate(urls):
                image_path = os.path.join(bib_dir, f"image_{i}.jpeg")
                if not self.downloader.download(url, image_path):
                    print(f"Failed to download image from {url}") 