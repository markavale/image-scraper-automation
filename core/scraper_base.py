from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class ScraperStrategy(ABC):
    """Abstract base class for scraper strategies"""
    
    @abstractmethod
    def scrape(self, url: str) -> Optional[Dict[Any, Any]]:
        """
        Scrape data from the given URL
        
        Args:
            url: The URL to scrape from
            
        Returns:
            Optional[Dict]: The scraped data as a dictionary, or None if scraping failed
        """
        pass 