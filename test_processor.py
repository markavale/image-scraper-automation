#!/usr/bin/env python3

import asyncio
import os
import shutil
from playwright.async_api import async_playwright
from core.downloader import ImageProcessor, VPNManager, logger
import logging

# Configure logging to show more details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create a test directory for output
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Function to download sample images if not available
async def download_sample_images(num_images=4):
    """Download sample images for testing if not already available."""
    # Create a directory for sample images
    sample_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_images")
    os.makedirs(sample_dir, exist_ok=True)
    
    # Sample image URLs
    image_urls = [
        "https://source.unsplash.com/random/800x600/?nature",
        "https://source.unsplash.com/random/800x600/?city",
        "https://source.unsplash.com/random/800x600/?people",
        "https://source.unsplash.com/random/800x600/?technology"
    ]
    
    image_paths = []
    
    # Use playwright to download images
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        
        for i, url in enumerate(image_urls[:num_images]):
            image_path = os.path.join(sample_dir, f"sample_image_{i+1}.jpg")
            image_paths.append(image_path)
            
            # Skip if image already exists
            if os.path.exists(image_path):
                logger.info(f"Sample image already exists: {image_path}")
                continue
                
            try:
                logger.info(f"Downloading sample image from {url}")
                await page.goto(url)
                
                # Take a screenshot and save as the sample image
                await page.screenshot(path=image_path)
                logger.info(f"Downloaded sample image: {image_path}")
            except Exception as e:
                logger.error(f"Failed to download sample image {i+1}: {str(e)}")
        
        await browser.close()
    
    return image_paths

async def test_image_processor(image_paths):
    """Process multiple images to demonstrate IP rotation."""
    processed_paths = []
    
    # Reset the request counter to ensure we start fresh
    ImageProcessor.request_count = 0
    
    async with async_playwright() as playwright:
        for i, image_path in enumerate(image_paths):
            logger.info(f"Processing image {i+1}/{len(image_paths)}: {image_path}")
            logger.info(f"Current request count: {ImageProcessor.request_count}")
            
            # Create processor for this image
            processor = ImageProcessor(image_path, OUTPUT_DIR)
            
            try:
                # Process the image
                processed_path = await processor.process_image(playwright)
                processed_paths.append(processed_path)
                
                logger.info(f"Successfully processed image {i+1}: {processed_path}")
                logger.info(f"New request count: {ImageProcessor.request_count}")
                
                # Wait a bit between processing
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing image {i+1}: {str(e)}")
    
    return processed_paths

async def test_vpn_manager():
    """Test the VPN manager functionality directly."""
    vpn_manager = VPNManager()
    
    logger.info("Testing VPN Manager...")
    
    # Check if Windscribe is installed
    logger.info("Checking if Windscribe is installed")
    installed = vpn_manager._check_windscribe_installed()
    logger.info(f"Windscribe installed: {installed}")
    
    if not installed:
        logger.warning("Windscribe not installed. Skipping VPN tests.")
        return
    
    # Test connection
    logger.info("Testing connection to Windscribe")
    connected = vpn_manager.connect()
    logger.info(f"Connected to Windscribe: {connected}")
    
    # Wait a bit
    await asyncio.sleep(5)
    
    # Test IP rotation
    logger.info("Testing IP rotation")
    rotated = vpn_manager.rotate_ip()
    logger.info(f"IP rotated: {rotated}")
    
    # Test disconnection
    logger.info("Testing disconnection from Windscribe")
    disconnected = vpn_manager.disconnect()
    logger.info(f"Disconnected from Windscribe: {disconnected}")

async def main():
    """Main function to run all tests."""
    # Print header
    print("\n" + "="*50)
    print("IMAGE PROCESSOR AND VPN ROTATION TESTER")
    print("="*50 + "\n")
    
    # Test VPN manager
    await test_vpn_manager()
    
    # Download sample images if needed
    print("\n" + "="*50)
    print("DOWNLOADING SAMPLE IMAGES")
    print("="*50 + "\n")
    image_paths = await download_sample_images(4)
    
    if not image_paths:
        logger.error("No sample images available for testing")
        return
    
    # Process images and demonstrate IP rotation
    print("\n" + "="*50)
    print("PROCESSING IMAGES WITH IP ROTATION")
    print("="*50 + "\n")
    processed_paths = await test_image_processor(image_paths)
    
    # Print summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    print(f"Total images processed: {len(processed_paths)}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Final request count: {ImageProcessor.request_count}")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(main())

