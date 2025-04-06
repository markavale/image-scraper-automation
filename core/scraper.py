from typing import Optional, Dict, Any
from .scraper_base import ScraperStrategy

class Scraper:
    """Context class that uses scraper strategies"""
    
    def __init__(self, strategy: ScraperStrategy):
        """
        Initialize the scraper with a strategy
        
        Args:
            strategy: The scraping strategy to use
        """
        self._strategy = strategy
    
    def set_strategy(self, strategy: ScraperStrategy) -> None:
        """
        Change the scraping strategy
        
        Args:
            strategy: The new scraping strategy to use
        """
        self._strategy = strategy
    
    def scrape(self, url: str) -> Optional[Dict[Any, Any]]:
        """
        Scrape data using the current strategy
        
        Args:
            url: The URL to scrape from
            
        Returns:
            Optional[Dict]: The scraped data as a dictionary, or None if scraping failed
        """
        return self._strategy.scrape(url) 