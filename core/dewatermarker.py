import asyncio
import os
import logging
from typing import List
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from core.downloader import ImageProcessor, VPNManager


# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Dewatermarker:
    # Class variable to track requests across all instances
    request_count = 0
    
    def __init__(self, output_base_dir: str = "media/processed", timeout: int = 60000, 
                 max_requests_before_rotation: int = 3):
        """
        Initializes the Dewatermarker.

        Args:
            output_base_dir (str): The base directory to save processed images.
                                   Subdirectories will be created based on the input structure.
            timeout (int): Maximum time in milliseconds to wait for operations.
            max_requests_before_rotation (int): Number of requests before rotating IP.
        """
        self.output_base_dir = output_base_dir
        self.timeout = timeout
        self.max_requests_before_rotation = max_requests_before_rotation
        self.vpn_manager = VPNManager()
        os.makedirs(self.output_base_dir, exist_ok=True)
        logger.info(f"Initialized Dewatermarker. Processed images will be saved under {self.output_base_dir}")
        logger.info(f"IP rotation will occur every {self.max_requests_before_rotation} requests")
    async def _process_single_image(self, page, image_path: str) -> str | None:
        """Helper function to process a single image."""
        original_filename = os.path.basename(image_path)
        original_subfolder = os.path.basename(os.path.dirname(image_path)) # e.g., bib_number
        output_dir = os.path.join(self.output_base_dir, original_subfolder)
        os.makedirs(output_dir, exist_ok=True)
        
        processed_image_path = None # Initialize

        logging.info(f"Processing image: {image_path}")
        try:
            await page.goto("https://dewatermark.ai/", timeout=self.timeout)
            
            # Wait for the file input element to be ready and upload the file
            file_input_selector = "input[type='file']"
            await page.wait_for_selector(file_input_selector, state="attached", timeout=self.timeout)
            # It's often more reliable to use set_input_files directly if the input is not hidden
            # If the button *must* be clicked to reveal the input, uncomment the lines below
            # async with page.expect_file_chooser(timeout=self.timeout) as fc_info:
            #     await page.locator("//button[contains(., 'Upload Image')]").click() # Adjust locator if needed
            # file_chooser = await fc_info.value
            # await file_chooser.set_files(image_path)
            await page.locator(file_input_selector).set_input_files(image_path)
            
            logging.info(f"Uploaded {original_filename} to dewatermark.ai")

            # Wait for processing and the download button to appear
            # Wait for processing and the download button to appear
            # Use CSS selector with button role to target the regular Download button (not PRO)
            # First, wait for the download buttons to appear after processing
            await page.wait_for_selector("button:has-text('Download')", state="visible", timeout=self.timeout * 3)
            logging.info(f"Dewatermarking complete for {original_filename}. Starting download.")

            # Turn off strict mode for this operation to handle multiple matches
            page.set_default_timeout(self.timeout * 2)
            await page.locator("button:has-text('Download')").first.wait_for(state="visible")
            
            # Find the specific download button (not PRO) using role and name
            download_button = page.get_by_role("button", name="Download", exact=True)

            # Check if button is enabled and wait if needed with better status tracking
            max_wait_time = self.timeout * 2  # Maximum wait time (120 seconds by default)
            max_retries = 30  # Maximum number of retry attempts
            retry_count = 0
            poll_interval = 2  # Poll every 2 seconds
            wait_start_time = asyncio.get_event_loop().time()
            
            # Common processing completion indicators
            completion_indicators = [
                "Processing complete", "Ready to download", "Finished", "100%"
            ]
            
            # Get initial button state and UI status
            is_button_disabled = await download_button.is_disabled()
            
            # Capture the HTML state for analysis
            html_state = await page.content()
            logging.debug(f"Initial page state captured ({len(html_state)} bytes)")

            # Log the initial button state with more details
            button_class = await download_button.get_attribute("class")
            button_text = await download_button.inner_text()
            logging.info(f"Download button state: disabled={is_button_disabled}, text='{button_text}', class='{button_class}'")
            
            while is_button_disabled and retry_count < max_retries:
                elapsed = (asyncio.get_event_loop().time() - wait_start_time) * 1000  # Convert to ms
                retry_count += 1
                
                if elapsed >= max_wait_time:
                    logging.warning(f"Download button still disabled after {int(elapsed/1000)}s - maximum wait time reached")
                    break
                
                logging.info(f"Download button is disabled, waiting... (Attempt {retry_count}/{max_retries}, {int(elapsed/1000)}s elapsed)")
                
                # Check for processing status indicators
                processing_completed = False
                try:
                    # Check multiple status elements that might indicate completion
                    status_selectors = [".status-text", ".processing-status", ".result-status", ".status-indicator"]
                    
                    for selector in status_selectors:
                        try:
                            if await page.locator(selector).count() > 0:
                                status = await page.locator(selector).first.text_content()
                                if status:
                                    logging.info(f"Status found ({selector}): {status}")
                                    # Check if any completion indicator is in the status text
                                    if any(indicator.lower() in status.lower() for indicator in completion_indicators):
                                        logging.info(f"Processing appears complete based on status text: {status}")
                                        processing_completed = True
                        except Exception:
                            continue
                    
                    # Check if button has become enabled during status check
                    is_button_disabled = await download_button.is_disabled()
                    if not is_button_disabled:
                        logging.info("Download button is now enabled!")
                        break
                    
                    # If processing appears complete but button is still disabled, we'll
                    # try the fallback methods after a few more attempts
                    if processing_completed and retry_count > 10:
                        logging.info("Processing appears complete but button remains disabled, will try alternative methods soon")
                        # Give it a few more attempts before breaking
                        if retry_count > 15:
                            logging.warning("Breaking wait loop to try alternative download methods")
                            break
                        
                except Exception as status_error:
                    logging.warning(f"Error checking status: {status_error}")
                
                # Take a screenshot periodically to help with debugging
                if retry_count % 5 == 0:
                    try:
                        debug_screenshot = os.path.join(output_dir, f"debug_{original_filename}_attempt_{retry_count}.png")
                        await page.screenshot(path=debug_screenshot)
                        logging.info(f"Saved debug screenshot: {debug_screenshot}")
                    except Exception as ss_error:
                        logging.warning(f"Failed to save debug screenshot: {ss_error}")
                
                # Wait before next check
                await asyncio.sleep(poll_interval)
                
                # Update the button state
                is_button_disabled = await download_button.is_disabled()

            # Attempt download even if button appears disabled (some sites have UI quirks)
            try:
                # Log final button state before attempting click
                is_button_disabled = await download_button.is_disabled()
                logging.info(f"Attempting download with button in state: disabled={is_button_disabled}")
                
                # If the button is still disabled after waiting, check if the page indicates we're
                # on a free tier with limits - this might help explain why the button stays disabled
                if is_button_disabled:
                    logging.info("Button still disabled, checking if we've hit usage limits...")
                    
                    # Look for common limit indicators in the page content
                    limit_indicators = [
                        "free account", "subscription required", "limit reached", 
                        "try premium", "upgrade account", "login required"
                    ]
                    
                    page_text = await page.evaluate("() => document.body.innerText")
                    found_limits = [indicator for indicator in limit_indicators if indicator.lower() in page_text.lower()]
                    
                    if found_limits:
                        logging.warning(f"Found potential usage limit indicators: {', '.join(found_limits)}")
                    
                # Try a JavaScript click first if button is disabled, which might bypass disabled state
                if is_button_disabled:
                    try:
                        logging.info("Attempting JavaScript click to bypass disabled state...")
                        await page.evaluate("""() => {
                            const buttons = Array.from(document.querySelectorAll('button'));
                            const downloadBtn = buttons.find(b => 
                                b.textContent.includes('Download') && 
                                !b.textContent.includes('PRO')
                            );
                            if (downloadBtn) {
                                downloadBtn.disabled = false;
                                downloadBtn.click();
                                return true;
                            }
                            return false;
                        }""")
                        # Brief wait to see if download starts after JS click
                        await asyncio.sleep(2)
                    except Exception as js_error:
                        logging.warning(f"JavaScript click attempt failed: {js_error}")
                
                # Now use the standard Playwright download handler
                async with page.expect_download(timeout=self.timeout) as download_info:
                    # Use force option to try clicking even if the button appears disabled
                    await download_button.click(force=True, timeout=self.timeout)
                
                # Get the download from the context manager
                download = await download_info.value
                
                # Verify that the download was successful
                if download.failure():
                    raise Exception(f"Download failed: {download.failure()}")
                
                # Construct save path using the original subfolder structure
                # Use suggested_filename if available, otherwise fallback
                suggested_filename = download.suggested_filename or f"processed_{original_filename}"
                processed_image_path = os.path.join(output_dir, suggested_filename)
                
                # Save the downloaded file
                await download.save_as(processed_image_path)
                
                # Verify the file exists and has content
                if os.path.exists(processed_image_path) and os.path.getsize(processed_image_path) > 0:
                    logging.info(f"Successfully downloaded processed image to: {processed_image_path}")
                else:
                    raise Exception(f"Downloaded file is missing or empty: {processed_image_path}")
            except Exception as download_error:
                logging.error(f"Download error for {image_path}: {download_error}")
                raise download_error  # Re-raise to be caught by the outer try/except
            
        except PlaywrightTimeoutError as timeout_error:
            logging.error(f"Timeout error processing image: {image_path}. The website might be slow or selectors might have changed. Error: {timeout_error}")
        except Exception as e:
            error_message = str(e)
            # Handle various error scenarios
            if "strict mode violation" in error_message or "element is not enabled" in error_message:
                logging.error(f"Button interaction error for {image_path}. Trying alternative approaches...")
                
                # Try multiple alternative methods to download the processed image
                for attempt, method in enumerate(["css-selector", "js-click", "screenshot-fallback"]):
                    try:
                        logging.info(f"Attempt {attempt+1}: Trying method '{method}'")
                        
                        if method == "css-selector":
                            # Alternative 1: Use CSS selector with nth-child
                            download_button = page.locator("button:has-text('Download'):not(:has-text('PRO'))").first
                            await download_button.wait_for(state="visible", timeout=self.timeout)
                            async with page.expect_download(timeout=self.timeout) as download_info:
                                await download_button.click(force=True)
                        
                        elif method == "js-click":
                            # Alternative 2: Use JavaScript to click the button directly
                            await page.evaluate("""() => {
                                const buttons = Array.from(document.querySelectorAll('button'));
                                const downloadBtn = buttons.find(b => 
                                    b.textContent.includes('Download') && 
                                    !b.textContent.includes('PRO')
                                );
                                if (downloadBtn) {
                                    // Enable button if disabled
                                    downloadBtn.disabled = false;
                                    downloadBtn.click();
                                    return true;
                                }
                                return false;
                            }""")
                            
                            # Wait for download to start after JS click
                            async with page.expect_download(timeout=self.timeout) as download_info:
                                # Wait briefly to allow the download to initialize
                                await asyncio.sleep(2)
                        
                        elif method == "screenshot-fallback":
                            # Alternative 3: Save a screenshot as a fallback
                            fallback_path = os.path.join(output_dir, f"screenshot_{original_filename}.png")
                            await page.screenshot(path=fallback_path)
                            logging.info(f"Saved screenshot as fallback: {fallback_path}")
                            processed_image_path = fallback_path
                            return processed_image_path
                        
                        # If we got here with the first two methods, process the download
                        if method != "screenshot-fallback":
                            download = await download_info.value
                            
                            # Check if download was successful
                            if download.failure():
                                logging.warning(f"Download failed: {download.failure()}")
                                continue
                                
                            suggested_filename = download.suggested_filename or f"processed_{original_filename}"
                            processed_image_path = os.path.join(output_dir, suggested_filename)
                            await download.save_as(processed_image_path)
                            
                            # Verify file exists and has content
                            if os.path.exists(processed_image_path) and os.path.getsize(processed_image_path) > 0:
                                logging.info(f"Successfully downloaded processed image to: {processed_image_path}")
                            else:
                                logging.warning(f"Downloaded file is missing or empty: {processed_image_path}")
                                continue
                            return processed_image_path
                        
                    except Exception as alt_error:
                        logging.warning(f"Alternative method '{method}' failed: {alt_error}")
                
                logging.error("All alternative methods failed to download the processed image")
            else:
                logging.error(f"An error occurred processing {image_path}: {error_message}")
            # Clean up partial download if necessary - this is now handled in the download scope
            if processed_image_path and os.path.exists(processed_image_path) and os.path.getsize(processed_image_path) == 0:
                try:
                    os.remove(processed_image_path)
                    logging.info(f"Removed empty file: {processed_image_path}")
                except Exception as cleanup_e:
                    logging.error(f"Error during cleanup for {processed_image_path}: {cleanup_e}")
            
            # If we reached this point with an error, ensure None is returned
            if 'processed_image_path' not in locals() or processed_image_path is None or not os.path.exists(processed_image_path):
                processed_image_path = None

        return processed_image_path


    async def process_images(self, image_paths: List[str]) -> List[str]:
        """
        Processes a list of images using dewatermark.ai.

        Args:
            image_paths (List[str]): A list of absolute paths to the raw images.

        Returns:
            List[str]: A list of absolute paths to the successfully processed images.
        """
        processed_paths = []
        if not image_paths:
            logger.warning("No image paths provided to process.")
            return processed_paths

        # Reset the request counter to ensure we start fresh
        ImageProcessor.request_count = 0

        logger.info(f"Starting to process {len(image_paths)} images...")
        
        # First, check if Windscribe is installed for IP rotation
        windscribe_installed = self.vpn_manager._check_windscribe_installed()
        if windscribe_installed:
            logger.info("Windscribe is installed. IP rotation will be active.")
            # Make sure we have a fresh connection at the start
            if not self.vpn_manager.verify_connection_status():
                logger.info("Initial VPN connection not active, establishing connection...")
                self.vpn_manager.rotate_ip(force=True)
                # Wait a bit for the connection to stabilize
                await asyncio.sleep(3)
        else:
            logger.warning("Windscribe is not installed or not in PATH. IP rotation will be disabled.")
        
        async with async_playwright() as p:
            for i, image_path in enumerate(image_paths):
                if not os.path.exists(image_path):
                    logger.warning(f"Image path does not exist, skipping: {image_path}")
                    continue
                
                logger.info(f"Processing image {i+1}/{len(image_paths)}: {image_path}")
                logger.info(f"Current request count: {ImageProcessor.request_count}")
                
                # Check for IP rotation before processing
                if ImageProcessor.request_count >= self.max_requests_before_rotation and windscribe_installed:
                    logger.info(f"Request count reached {ImageProcessor.request_count}, rotating IP before processing...")
                    if self.vpn_manager.rotate_ip(force=True, max_retries=3):
                        logger.info("Successfully rotated IP")
                        # Reset counter after successful rotation
                        ImageProcessor.request_count = 0
                        # Wait for connection to stabilize
                        await asyncio.sleep(5)
                    else:
                        logger.warning("IP rotation failed, proceeding with current IP")
                        # Add additional wait time to reduce rate limiting risk
                        await asyncio.sleep(15)
                
                # Determine the output subdirectory to maintain folder structure
                original_subfolder = os.path.basename(os.path.dirname(image_path)) # e.g., bib_number
                output_dir = os.path.join(self.output_base_dir, original_subfolder)
                os.makedirs(output_dir, exist_ok=True)
                
                # Create processor for this image
                processor = ImageProcessor(image_path, output_dir)
                
                try:
                    # Process the image using our enhanced ImageProcessor
                    processed_path = await processor.process_image(p)
                    
                    if processed_path:
                        processed_paths.append(processed_path)
                        logger.info(f"Successfully processed image {i+1}: {processed_path}")
                        logger.info(f"New request count: {ImageProcessor.request_count}")
                    else:
                        logger.warning(f"Image processor returned None for {image_path}")
                        
                    # Wait a bit between processing to avoid overwhelming the server
                    await asyncio.sleep(3)  # Increased from 2 to 3 seconds
                    
                except Exception as e:
                    logger.error(f"Error processing image {i+1}: {str(e)}")
                    error_message = str(e).lower()
                    
                    # Check if it appears to be a rate limiting issue with more patterns
                    rate_limited = any(term in error_message for term in [
                        "rate", "limit", "429", "daily", "quota", "exceeded",
                        "too many", "try again", "tomorrow", "subscription"
                    ])
                    
                    if rate_limited:
                        logger.warning("Rate limiting definitely detected, trying to rotate IP...")
                        if windscribe_installed:
                            # Force reconnect on persistent limits
                            force_reconnect = "try again tomorrow" in error_message or "daily limit" in error_message
                            if self.vpn_manager.rotate_ip(force=True, force_reconnect=force_reconnect, max_retries=3):
                                # Reset counter after rotation due to rate limiting
                                ImageProcessor.request_count = 0
                                logger.info("Successfully rotated IP after rate limit detection")
                                # Wait longer before continuing after hitting a rate limit
                                await asyncio.sleep(15)  # Increased from 10 to 15 seconds
                            else:
                                logger.warning("Could not rotate IP despite rate limiting. Waiting much longer before continuing...")
                                await asyncio.sleep(45)  # Increased from 30 to 45 seconds when rotation fails
                        else:
                            logger.warning("Windscribe not available for IP rotation. Waiting longer before continuing...")
                            await asyncio.sleep(45)  # Longer wait if IP rotation not available
                    else:
                        # Still wait a bit for non-rate-limit errors
                        logger.info("Waiting before processing next image due to error...")
                        await asyncio.sleep(5)
            
            logger.info("Finished processing all images.")
            
        return processed_paths

# Example usage (optional, for testing)
async def _test():
    # Create dummy files for testing
    os.makedirs("media/raw/test_bib", exist_ok=True)
    dummy_raw_path = "media/raw/test_bib/dummy_image.png"
    
    # Create a proper test image if it doesn't exist
    if not os.path.exists(dummy_raw_path) or os.path.getsize(dummy_raw_path) < 1000:
        logger.info("Creating a proper test image...")
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a blank image with white background
            img = Image.new('RGB', (800, 600), color=(255, 255, 255))
            d = ImageDraw.Draw(img)
            
            # Draw some test text as a "watermark"
            try:
                font = ImageFont.truetype("Arial", 40)
            except IOError:
                # Fallback to default font
                font = ImageFont.load_default()
                
            d.text((200, 250), "TEST WATERMARK", fill=(200, 200, 200), font=font)
            d.text((250, 300), "Please Remove Me", fill=(200, 200, 200), font=font)
            
            # Save the image
            img.save(dummy_raw_path)
            logger.info(f"Created test image at {dummy_raw_path}")
        except Exception as e:
            logger.error(f"Error creating test image: {str(e)}")
            # Fallback to writing a basic file
            with open(dummy_raw_path, "wb") as f:
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00\x1f\xf3\xffa\x00\x00\x00\x01sRGB\x00\xae\xce\x1c\xe9\x00\x00\x00\x04gAMA\x00\x00\xb1\x8f\x0b\xfca\x05\x00\x00\x00\tpHYs\x00\x00\x0e\xc3\x00\x00\x0e\xc3\x01\xc7o\xa8d\x00\x00\x00\x0cIDATx^c\xf8\x0f\x04\x0c#\x11\x00\x00\x08\x00\x01\xcf\xad\xefY\x00\x00\x00\x00IEND\xaeB`\x82')  # Minimal valid PNG
