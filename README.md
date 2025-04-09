# Image Scraper Automation Pipeline

## Overview

This repository contains an automated pipeline for scraping images from GeoSnapshot (geosnapshot.com) and removing watermarks using dewatermark.ai. The system uses a combination of web scraping, browser automation, and VPN rotation to efficiently collect and process images.

## Key Features

- **GeoSnapshot Scraper**: Search for events and collect photos based on bib numbers
- **Automatic Image Processing**: Downloads raw images and removes watermarks using dewatermark.ai
- **VPN Integration**: Uses Windscribe VPN with IP rotation to avoid rate limits
- **Browser Automation**: Utilizes Playwright for reliable web interaction
- **Robust Error Handling**: Includes retry mechanisms, failure detection, and comprehensive logging

## System Components

- `PhotoProcessor`: Main orchestrator that coordinates the entire pipeline
- `Scraper`/`SearchScraperStrategy`: Locates events on GeoSnapshot based on keywords
- `PhotoCollector`: Gathers photo metadata from GeoSnapshot API
- `PhotoManager`: Handles downloading and organizing raw images
- `Dewatermarker`: Processes images through dewatermark.ai to remove watermarks
- `VPNManager`: Controls Windscribe VPN for IP rotation to avoid rate limiting

## Requirements

- Python 3.8+
- Playwright for browser automation
- Windscribe VPN CLI installed (for IP rotation functionality)
- PIL/Pillow for image processing

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install Playwright browsers:
   ```bash
   python -m playwright install
   ```
4. Ensure Windscribe CLI is installed and configured (optional, for VPN rotation)

## Usage

Run the pipeline using the command-line interface:

```bash
python . --bib_numbers "12345,67890" --keyword "marathon"
```

Options:
- `--bib_numbers`: Comma-separated list of bib numbers to search for
- `--keyword`: Keyword to search for events (e.g., "marathon", "race")
- `--use_jquery`: Use alternative jQuery-based scraping (optional)
- `--save_results`: Save raw metadata results to file (default: True)

## Directory Structure

- `/core`: Core components of the pipeline
- `/helpers`: Utility classes and functions
- `/media`: Storage for downloaded and processed images
  - `/media/raw`: Raw images before processing
  - `/media/processed`: Images after watermark removal
- `/logs`: Log files for debugging and monitoring

## Troubleshooting

- **Rate Limiting**: If you encounter frequent rate limits from dewatermark.ai, adjust the `max_requests_before_rotation` parameter in the Dewatermarker class
- **Image Processing Errors**: Check `/logs/error.log` for detailed error information
- **VPN Connection Issues**: Ensure Windscribe CLI is properly installed and authenticated

## License

For personal use only. This software is provided as-is with no warranty.
