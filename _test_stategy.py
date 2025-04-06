from core.scraper_strategy import SearchScraperStrategy


if __name__ == "__main__":

    keyword = "ctrl alt run"
    scraper = SearchScraperStrategy(keyword)

    print(scraper.events)