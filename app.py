import streamlit as st
import re
import os
import requests
from helpers.base_scraper import Scraper
from PIL import Image
from io import BytesIO
import cv2
import numpy as np
# from helpers.watermark_remover import remove_watermark

# Function to extract event IDs from the URL using regex
def extract_event_ids(url):
    # Regex to capture the last sequence of digits in the URL path
    return re.findall(r'/(\d+)(?:\?|$)', url)

# Function to scrape and download images
def scrape_and_download_images(event_ids, bib_number):
    scraper = Scraper()
    photos_by_bib_number = {bib_number: []}

    for event_id in event_ids:
        url = f"https://geosnapshot.com/api/v1/events/{event_id}/photos?page=1&photo_text={bib_number}&user_id=445617"
        
        while url:
            res = scraper._request(method="GET", url=url)
            res_payload = res.json()
            
            # Collect zoomImg URLs for the current bib_number
            photos_by_bib_number[bib_number].extend(
                photo['zoomImg'] for photo in res_payload.get('photos', [])
                if 'zoomImg' in photo
            )
            
            # Check if there is a next page
            next_page = res_payload.get('meta', {}).get('nextPage')
            if next_page:
                # Update the URL to fetch the next page
                url = f"https://geosnapshot.com/api/v1/events/{event_id}/photos?page={next_page}&photo_text={bib_number}&user_id=445617"
            else:
                # No more pages to fetch
                url = None

    # Download images
    base_dir = "media"
    os.makedirs(base_dir, exist_ok=True)
    bib_dir = os.path.join(base_dir, bib_number)
    os.makedirs(bib_dir, exist_ok=True)

    downloaded_images = []  # List to store paths of downloaded images

    for i, url in enumerate(photos_by_bib_number[bib_number]):
        response = requests.get(url)
        if response.status_code == 200:
            image_path = os.path.join(bib_dir, f"image_{i}.jpeg")
            with open(image_path, "wb") as f:
                f.write(response.content)
            downloaded_images.append(image_path)  # Add image path to the list

    return downloaded_images  # Return paths of downloaded images

# Streamlit app
st.title("GeoSnapshot Image Scraper")

# Input fields
bib_number = st.text_input("Enter Bib Number:")
geosnapshot_url = st.text_input("Enter GeoSnapshot URL:")

if st.button("Scrape Images"):
    if bib_number and geosnapshot_url:
        event_ids = extract_event_ids(geosnapshot_url)
        if event_ids:
            st.write(f"Extracted Event IDs: {event_ids}")
            image_paths = scrape_and_download_images(event_ids, bib_number)
            st.write(f"Downloaded {len(image_paths)} images.")

            # Display images using Streamlit
            for image_path in image_paths:
                img = Image.open(image_path)
                st.image(img, caption=f"Bib Number: {bib_number}", use_column_width=True)
                
                # Optionally, provide a download button for each image
                with open(image_path, "rb") as file:
                    st.download_button(
                        label=f"Download {os.path.basename(image_path)}",
                        data=file,
                        file_name=os.path.basename(image_path),
                        mime="image/jpeg"
                    )
        else:
            st.error("No event IDs found in the URL.")
    else:
        st.error("Please enter both a Bib Number and a GeoSnapshot URL.")