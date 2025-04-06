from bs4 import BeautifulSoup
from helpers.windscribe_helpers import Windscribe
from playwright.sync_api import sync_playwright
import requests, json, base64, io

# Initialize a counter for the number of calls to remove_watermark
remove_watermark_call_count = 0

import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
async def main():
    async with async_playwright() as p:
        # Launch the browser
        browser = await p.chromium.launch(headless=False)
        # Open a new page
        page = await browser.new_page()

        # Register the Playwright Stealth plugin
        await stealth_async(page)

        # Visit the target page
        await page.goto("https://arh.antoinevastel.com/bots/areyouheadless")

        # Extract the message contained on the page
        message_element = page.locator("#res")
        message = await message_element.text_content()

        # Print the resulting message
        print(f'The result is: "{message}"')

        # Prepare the API call
        url = "https://api.dewatermark.ai/api/object_removal/v5/erase_watermark"
        image_path = 'media/5564/image_0.jpeg'

        # The image data from your payload
        # image_data = b"""[Your binary data here]"""

        # Ensure the image data is correct
        # image_data = image_data.replace(b'\n', b'').replace(b' ', b'')

        with open(image_path, 'rb') as image_file:
            image_data2 = image_file.read()

        # Create a BytesIO object
        # img_file = io.BytesIO(image_data2)

        # Open the image file in binary mode
        with open("image.jpg", 'wb') as image_file:
            image_file.write(image_data2)

        with open("image.jpg", 'rb') as image_file:
            image_data = image_file.read()

        print(type(image_data))
        # Prepare the payload as form data
        payload = {
            'original_preview_image': ('image.jpg', image_data, 'image/jpeg'),
            'zoom_factor': '2'
        }

        # Set headers to mimic a normal user
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br',
            'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJpZ25vcmUiLCJwbGF0Zm9ybSI6IndlYiIsImlzX3BybyI6ZmFsc2UsImV4cCI6MTczMDcyMDUwN30.ZH3hyQwy1kdJDXg42iSv_nJaBvaYUcYDnAz_LKs6nes'  # Example for Bearer token
        }

        print("Starting API request...")
        # Use Playwright's request feature to send a POST request
        response = await page.request.post(url, multipart=payload, headers=headers)
        print(response.status, "Status code here....")
        if response.ok:
            print(await response.json(), "json res here...")
        else:
            print(f"Failed to remove watermark, status code: {response.status}")
            print(await response.json())

        # Close the browser and release its resources
        await browser.close()

# asyncio.run(main())


def remove_watermark(image_path):
    global remove_watermark_call_count
    remove_watermark_call_count += 1

    # Check if it's time to rotate the IP
    if remove_watermark_call_count % 3 == 0:
        get_windscribe_ip()
    
    url = "https://api.dewatermark.ai/api/object_removal/v5/erase_watermark"
    # https://api.dewatermark.ai/api/object_removal/v5/erase_watermark


    # Prepare the Playwright environment 
    with sync_playwright() as p:
        # Using chromium; this can be changed to firefox or webkit as needed
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Open the image file in binary mode
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
            
        # Ensure the image data is correct
        image_data = image_data.replace(b'\n', b'').replace(b' ', b'')

        # Create a BytesIO object
        img_file = io.BytesIO(image_data)

        # Prepare the payload as form data
        files = {
            'original_preview_image': ('image.jpg', img_file, 'image/jpeg'),
            'zoom_factor': '2'
        }

        payload = {
            'zoom_factor': '2'
        }

        # Set headers to mimic a normal user
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br',
            'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJpZ25vcmUiLCJwbGF0Zm9ybSI6IndlYiIsImlzX3BybyI6ZmFsc2UsImV4cCI6MTczMDcyMDUwN30.ZH3hyQwy1kdJDXg42iSv_nJaBvaYUcYDnAz_LKs6nes'  # Example for Bearer token
        }

        print("Starting request.....")
        # Use Playwright's request feature to send a POST request
        response = page.request.post(url, multipart=files, headers=headers)
        print(response.status, "Status code here....")
        print(response.__dict__)
        print(response.json(), "json res here...")
        # Check if the request was successful
        if response.ok:
            return response.json()
        else:
            return f"Failed to remove watermark, status code: {response.status}"
        
        # Close the browser
        browser.close()

def get_my_ip():
    # URL of the website to scrape
    url = "https://ifconfig.me/"
    
    # Send a GET request to the website
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        # Find the element containing the IP address
        ip_address = soup
        
        return ip_address
    else:
        return "Failed to retrieve IP address"

def reboot_windscribe():
    # Stop Windscribe
    subprocess.run(['windscribe-cli', 'disconnect'], check=True)
    # Start Windscribe
    subprocess.run(['windscribe-cli', 'connect'], check=True)
    print("Windscribe has been rebooted.")

import os, subprocess
def parse_windscribe_status(output):
    # Split the output into lines
    lines = output.strip().split('\n')
    
    # Initialize an empty dictionary
    status_dict = {}
    
    # Iterate over each line
    for line in lines:
        # Split each line into key and value
        if ':' in line:
            key, value = line.split(':', 1)
            # Strip whitespace and store in the dictionary
            status_dict[key.strip()] = value.strip()
    
    return status_dict

def get_windscribe_status():
    result = subprocess.run(['windscribe-cli', 'status'], capture_output=True, text=True)
    return parse_windscribe_status(result.stdout)

def get_windscribe_ip():
    try:
        print(get_windscribe_status(), "res here...")
        my_ip = get_my_ip()
        print(f"My IP address is: {my_ip}")
        vpn = Windscribe('servers.txt', 'markavale', '@Linux121598')
        print(get_windscribe_status(), "res here...")
        vpn.connect("BBQ", rand=True)
        my_ip_2 = get_my_ip()
        print(f"My IP address is: {my_ip_2}")
    except Exception as e:
        print(e, "error here...")
        reboot_windscribe()

# get_windscribe_ip()

def remove_watermark2(image_path):
    global remove_watermark_call_count
    remove_watermark_call_count += 1

    # Check if it's time to rotate the IP
    if remove_watermark_call_count % 3 == 0:
        get_windscribe_ip()

    url = "https://api.dewatermark.ai/api/object_removal/v5/erase_watermark"
    
    # Open the image file in binary mode
    with open(image_path, 'rb') as image_file:
        image_data = image_file.read()
    
    # Prepare the payload
    payload = {
        'original_preview_image': image_data,
        'zoom_factor': 2
    }
    
    # Set headers to mimic a normal user
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    print("Starting to request...")
    # Send the POST request
    response = requests.post(url, files=payload, headers=headers)
    print(response.status_code, "Status code ghere....")
    # Check if the request was successful
    if response.status_code == 200:
        return response.json()
    else:
        return f"Failed to remove watermark, status code: {response.status_code}"

# def get_windscribe_ip():
#     vpn = Windscribe('servers.txt', 'markavale', '@Linux121598')
#     vpn.locations()
#     vpn.connect("BBQ", rand=True)
get_windscribe_ip()
# Example usage
# result = remove_watermark('media/5564/image_0.jpeg')
# with open("result.json", "w") as f:
#     json.dump(result, f)





# # # Example usage
# my_ip = get_my_ip()
# print(f"My IP address is: {my_ip}")

# get_windscribe_ip()

# my_ip_2 = get_my_ip()
# print(f"My IP address is: {my_ip_2}")