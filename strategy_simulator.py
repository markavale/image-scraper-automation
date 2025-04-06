from core.scraper import Scraper
from core.scraper_strategy import JSONPScraperStrategy


def geo_snapshot_scraper(term: str):
     # The target URL endpoint (note: you may add a value for 'limit' if needed)
    url = ("https://geosnapshot.com/search/search?"
           "callback=jQuery112408828452522157875_1739275630919&term=Apollo&types%5B%5D=events&limit=")

    scraper = JSONPScraperStrategy()
    data = scraper.scrape(url)
    if data is None:
        exit(1)

    # Navigate to the events list in the response
    events = data.get('results', {}).get('events', [])
    if not events:
        print("No events found in the response.")
    else:
        for event in events:
            term = event.get('term')
            event_id = event.get('id')
            score = event.get('score')
            event_data = event.get('data', {})
            link = event_data.get('link')
            date = event_data.get('date')

            print(f"Event Term: {term}")
            print(f"Event ID: {event_id}")
            print(f"Score: {score}")
            print(f"Link: {link}")
            print(f"Date: {date}")
            print("-" * 40)

if __name__ == "__main__":
    geo_snapshot_scraper("Apollo")
    