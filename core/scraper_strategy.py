import requests
import json
from typing import Optional, Dict, Any, List
from .scraper_base import ScraperStrategy

class JSONPScraperStrategy(ScraperStrategy):
    """Strategy for scraping JSONP responses"""
    
    def scrape(self, url: str) -> Optional[Dict[Any, Any]]:
        """
        Fetches the JSONP response from the given URL, removes the callback wrapper,
        and returns the parsed JSON data as a Python dictionary.
        """
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad status codes
        except requests.RequestException as e:
            print(f"Error fetching URL: {e}")
            return None

        # The response is wrapped in a JSONP callback like:
        # jQuery112408828452522157875_1739275630919({...});
        text = response.text.strip()

        # Find the indices of the first '(' and the last ')'
        start = text.find('(')
        end = text.rfind(')')
        if start == -1 or end == -1:
            print("The response does not appear to be in valid JSONP format.")
            return None

        # Extract the JSON string and parse it
        json_str = text[start+1:end]
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return None

        return data

class SearchScraperStrategy(ScraperStrategy):
    """Strategy for scraping JSONP responses"""
    
    _URL = "https://geosnapshot.com/api/v1/search_events/keywords?q={}"
    _JQUERY_URL = "https://geosnapshot.com/search/search?callback=jQuery112406364163379823502_1740212483622&term={}&types%5B%5D=events&limit="

    def __init__(self, query: str, use_jquery: bool = False):
        self.use_jquery = use_jquery
        self.events = self._get_events(self.scrape(query))

    def scrape(self, query: str) -> Optional[Dict[Any, Any]]:
        """
        Fetches the JSONP response from the given URL, removes the callback wrapper,
        and returns the parsed JSON data as a Python dictionary.
        """
        url = self._URL.format(query) if not self.use_jquery else self._JQUERY_URL.format(query)
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching URL: {e}")
            return None

        text = response.text.strip()
        
        # Handle JSONP response if present
        if 'jQuery' in text:
            start = text.find('(')
            end = text.rfind(')')
            if start == -1 or end == -1:
                print("The response does not appear to be in valid JSONP format.")
                return None
            text = text[start+1:end]

        # Extract the JSON string and parse it
        try:    
            data = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return None

        return data
    
    def _get_events(self, data: Dict[Any, Any]) -> List[str]:
        if self.use_jquery:
            events = data.get('results', [{"events": []}])['events']#.get("events", [])
        else:
            events = data.get('events', [])
        ids = [event.get('id', None) for event in events]
        return list(set(filter(None, ids)))