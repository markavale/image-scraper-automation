from playwright.async_api import Playwright
import os
import subprocess
import asyncio
import logging
import time
import re
from io import BytesIO
from PIL import Image
import mimetypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VPNManager:
    """
    Manages Windscribe VPN connections for IP rotation.
    """
    # Available Windscribe locations to cycle through
    LOCATIONS = ["US", "CA", "UK", "DE", "FR", "NL", "CH", "SE", "NO", "IT"]
    
    def __init__(self):
        self.connected = False
        self.current_location_index = 0
        self.installed = self._check_windscribe_installed()
        self.rotation_attempts = 0  # Track consecutive rotation attempts
        self.max_consecutive_failures = 3  # After this many consecutive failures, attempt service restart
        # Verify initial connection status
        self.verify_connection_status()
    
    def _check_windscribe_installed(self):
        """Verify that Windscribe CLI is installed."""
        try:
            result = subprocess.run(["which", "windscribe"], capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("Windscribe CLI not found. Please install Windscribe and configure it.")
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking Windscribe installation: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from Windscribe VPN."""
        try:
            logger.info("Disconnecting from Windscribe VPN...")
            result = subprocess.run(["windscribe", "disconnect"], 
                                    capture_output=True, 
                                    text=True)
            if result.returncode == 0:
                logger.info("Successfully disconnected from Windscribe")
                self.connected = False
                return True
            else:
                logger.error(f"Failed to disconnect from Windscribe: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error while disconnecting from Windscribe: {str(e)}")
            return False
    
    def verify_connection_status(self):
        """
        Verify current Windscribe connection status.
        Updates the connected property and returns connection state.
        """
        try:
            logger.info("Checking Windscribe connection status...")
            result = subprocess.run(["windscribe", "status"], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                output = result.stdout.lower()
                
                # Update connection state based on output
                if "connect state: connected" in output:
                    logger.info("Windscribe is currently connected")
                    self.connected = True
                    # Extract current location if available
                    if "connected to " in output:
                        location = output.split("connected to ")[1].split()[0]
                        logger.info(f"Current Windscribe location: {location}")
                    return True
                else:
                    logger.info("Windscribe is currently disconnected")
                    self.connected = False
                    return False
            else:
                logger.error(f"Failed to check Windscribe status: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error checking Windscribe status: {str(e)}")
            return False
    
    def get_next_location(self):
        """
        Get the next location in the rotation cycle.
        """
        location = self.LOCATIONS[self.current_location_index]
        self.current_location_index = (self.current_location_index + 1) % len(self.LOCATIONS)
        return location
    
    def connect(self, location=None):
        """
        Connect to Windscribe VPN, optionally specifying a location.
        Returns True if connection successful, False otherwise.
        """
        try:
            # First disconnect if already connected
            if self.connected:
                self.disconnect()
            
            logger.info(f"Connecting to Windscribe VPN{' to ' + location if location else ''}...")
            
            if location:
                cmd = ["windscribe", "connect", location]
            else:
                cmd = ["windscribe", "connect"]
                
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Successfully connected to Windscribe")
                
                # Verify the connection with a status check
                time.sleep(3)  # Give the connection more time to stabilize
                if self.verify_connection_status():
                    logger.info(f"Connection verified to Windscribe{' at ' + location if location else ''}")
                    return True
                else:
                    logger.warning("Connection attempt successful but status verification failed")
                    return False
            else:
                logger.error(f"Failed to connect to Windscribe: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error while connecting to Windscribe: {str(e)}")
            return False
    
    def rotate_ip(self, location=None, force=False, max_retries=3, force_reconnect=False):
        """
        Rotate IP by disconnecting and reconnecting to Windscribe.
        Returns True if rotation successful, False otherwise.
        
        Args:
            location: Optional specific location to connect to
            force: If True, forces a reconnection even if already connected
            max_retries: Maximum number of retry attempts if rotation fails
            force_reconnect: If True, will restart the windscribe service before attempting connection
        """
        logger.info("Rotating IP address...")
        
        # Track rotation attempts for monitoring potential service issues
        self.rotation_attempts += 1
        
        # If we've had too many consecutive failures, try to restart the service
        if self.rotation_attempts >= self.max_consecutive_failures or force_reconnect:
            logger.warning(f"Multiple rotation failures detected ({self.rotation_attempts}). Attempting to restart Windscribe service...")
            self._restart_windscribe_service()
            # Reset the counter after service restart attempt
            self.rotation_attempts = 0
            # Always disconnect after service restart
            self.disconnect()
            # Force a new connection regardless of current state
            force = True
        
        # If not forcing rotation and already verified as connected, skip disconnect
        if not force and self.verify_connection_status():
            logger.info("Already connected, using force=False so skipping reconnection")
            return True
            
        # Choose next location in rotation if none specified
        if not location:
            location = self.get_next_location()
            logger.info(f"Selected next location in rotation: {location}")
        
        # Try to disconnect first if already connected
        retry_count = 0
        rotation_successful = False
        
        while not rotation_successful and retry_count <= max_retries:
            try:
                # First disconnect (if already connected)
                if self.connected or not self.verify_connection_status():
                    logger.info(f"Disconnecting from current connection (retry {retry_count})")
                    disconnect_result = self.disconnect()
                    if not disconnect_result:
                        logger.warning("Failed to disconnect during IP rotation - trying a forced disconnect")
                        # Try a force disconnect if regular disconnect failed
                        self._force_disconnect()
                
                # Small delay between disconnect and connect
                time.sleep(3)  # Increased delay between operations
                
                # Try to connect with the selected location
                logger.info(f"Connecting to {location} (retry {retry_count})")
                connection_success = self.connect(location)
                
                if connection_success:
                    # Verify the connection with a status check
                    logger.info("Verifying new connection and IP address")
                    if self.verify_connection_status():
                        logger.info(f"Successfully rotated IP to {location}")
                        rotation_successful = True
                        # Reset rotation attempts counter on success
                        self.rotation_attempts = 0
                        return True
                    else:
                        logger.warning("Connection reported success but verification failed")
                else:
                    logger.warning(f"Failed to connect to {location}")
                    
                    # Try a different location on the next retry
                    if retry_count < max_retries:
                        location = self.get_next_location()
                        logger.info(f"Will try different location on next attempt: {location}")
            
            except Exception as e:
                logger.error(f"Error during IP rotation: {str(e)}")
                
            # Increment retry counter if not successful
            if not rotation_successful:
                retry_count += 1
                if retry_count <= max_retries:
                    logger.info(f"Retry {retry_count}/{max_retries} after waiting...")
                    time.sleep(5 * retry_count)  # Increased wait time with each retry
        
        # If we get here and still haven't succeeded, try one last connection without location
        if not rotation_successful:
            logger.warning("Failed to rotate IP with specific locations, trying auto-connect")
            # Try a final attempt without specifying location (let Windscribe choose best server)
            connection_success = self.connect()
            if connection_success and self.verify_connection_status():
                logger.info("Successfully connected with auto-selected location")
                # Reset rotation attempts counter on success
                self.rotation_attempts = 0
                return True
            else:
                logger.error("All IP rotation attempts failed")
                return False
                
    def _force_disconnect(self):
        """Force disconnect when normal disconnect fails"""
        try:
            logger.info("Attempting forced Windscribe disconnect...")
            # Try using windscribe-cli directly which can be more reliable
            result = subprocess.run(["windscribe-cli", "disconnect"], 
                                capture_output=True, text=True, timeout=10)
            if "DISCONNECTED" in result.stdout.upper():
                logger.info("Successfully force disconnected from Windscribe")
                self.connected = False
                return True
            else:
                logger.warning(f"Force disconnect gave unexpected output: {result.stdout}")
                return False
        except Exception as e:
            logger.error(f"Error during forced disconnect: {str(e)}")
            return False
    
    def _restart_windscribe_service(self):
        """Attempt to restart the Windscribe service when rotation is failing"""
        try:
            logger.info("Attempting to restart Windscribe service...")
            # First try to properly stop and restart the client
            subprocess.run(["windscribe", "logout"], capture_output=True, timeout=10)
            subprocess.run(["windscribe", "disconnect"], capture_output=True, timeout=10)
            time.sleep(2)
            
            # Try to restart the service (this approach varies by OS)
            # For macOS
            subprocess.run(["killall", "windscribe"], capture_output=True)
            time.sleep(2)
            
            # Restart and login again
            login_result = subprocess.run(["windscribe", "login"], 
                                      capture_output=True, text=True, timeout=20)
            
            if "logged in" in login_result.stdout.lower():
                logger.info("Successfully restarted Windscribe service and logged in")
                return True
            else:
                logger.warning("Windscribe service restart attempt completed, but login status unclear")
                return True  # Return true anyway so the system can try to connect
                
        except Exception as e:
            logger.error(f"Error restarting Windscribe service: {str(e)}")
            return False

class ImageProcessor:
    # Class variable to track dewatermark requests across all instances
    request_count = 0
    vpn_manager = VPNManager()
    
    def __init__(self, input_file_path: str, output_directory: str):
        self.input_file_path = input_file_path
        self.output_directory = output_directory
        self.max_requests_before_rotation = 3
        self.max_retries = 4  # Increased from 3 to 4 for more resilience
        self.daily_limit_detected = False
        self.disabled_download_retries = 2  # Number of retries when download button is disabled
        
        # Create output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)
        
        # Generate output file path
        base_name = os.path.basename(input_file_path)
        name_without_ext = os.path.splitext(base_name)[0]
        self.output_file_path = os.path.join(output_directory, f"{name_without_ext}_dewatermarked.jpg")  # Default extension, will be updated based on actual format
    async def _detect_image_format_and_save(self, binary_data, output_path):
        """
        Detects the image format from binary data and saves it with the appropriate extension.
        Returns the path to the saved image.
        """
        try:
            # Use PIL to open the image from binary data
            img = Image.open(BytesIO(binary_data))
            # Fix: Ensure we're calling lower() on a string by explicitly converting img.format to string first
            format_lower = str(img.format).lower() if img.format else "jpeg"  # Default to jpeg if format detection fails
            
            # Update file extension based on detected format
            base_path = os.path.splitext(output_path)[0]
            new_path = f"{base_path}.{format_lower}"
            
            # Save the image to the file system
            with open(new_path, 'wb') as f:
                f.write(binary_data)
            
            logger.info(f"Image saved successfully as {new_path} in {format_lower} format")
            return new_path
        except Exception as e:
            logger.error(f"Error processing image format: {str(e)}")
            # Fallback to saving the binary data as is
            with open(output_path, 'wb') as f:
                f.write(binary_data)
            logger.info(f"Image saved as raw binary data to {output_path}")
            return output_path
    
    async def _maybe_rotate_ip(self, force=False, force_reconnect=False):
        """
        Check if we need to rotate IP and do so if needed.
        
        Args:
            force: If True, forces an IP rotation regardless of counter
            force_reconnect: If True, forces a reconnection of the VPN service
        """
        # If force rotation or if daily limit was detected
        if force or self.daily_limit_detected:
            logger.info(f"{'Forced' if force else 'Daily limit triggered'} IP rotation")
            if ImageProcessor.vpn_manager.rotate_ip(force=True, force_reconnect=force_reconnect):
                logger.info("IP rotation completed successfully")
                # Reset counter and daily limit flag
                ImageProcessor.request_count = 0
                self.daily_limit_detected = False
                return True
            else:
                logger.warning("IP rotation failed despite forced attempt")
                return False
        
        # Ensure VPN is connected before proceeding
        if not ImageProcessor.vpn_manager.verify_connection_status():
            logger.warning("VPN disconnected, reconnecting...")
            if not ImageProcessor.vpn_manager.connect():
                logger.error("Failed to connect VPN, processing may be affected")
        
        # Normal counter-based rotation
        # Increment the class-level request counter
        ImageProcessor.request_count += 1
        
        # Check if we need to rotate the IP (every Nth request)
        if ImageProcessor.request_count >= self.max_requests_before_rotation:
            logger.info(f"Request count reached {ImageProcessor.request_count}, rotating IP...")
            if ImageProcessor.vpn_manager.rotate_ip(force_reconnect=force_reconnect):
                logger.info("IP rotation completed successfully")
                # Reset counter after successful rotation
                ImageProcessor.request_count = 0
                return True
            else:
                logger.warning("IP rotation failed, proceeding with current IP")
                return False
        
        return True  # No rotation needed or successful connection
    
    async def _upload_file(self, page, retry_count=0):
        """Handle file upload with multiple methods and verification."""
        logger.info(f"Attempting to upload file: {self.input_file_path}")
        
        # Verify the file exists and is accessible
        if not os.path.exists(self.input_file_path):
            raise FileNotFoundError(f"Input file not found: {self.input_file_path}")
        
        file_size = os.path.getsize(self.input_file_path)
        logger.info(f"Input file size: {file_size} bytes")
        
        if file_size == 0:
            raise ValueError(f"Input file is empty: {self.input_file_path}")
        
        # Method 1: Standard file input
        try:
            logger.info("Upload method 1: Using standard file input")
            
            # Wait for file input to be available with more specific selectors
            upload_selectors = [
                'input[type="file"][accept*="image"]',
                'input[type="file"]',
                '[type="file"]',
                'input[accept*="image"]'
            ]
            
            # Try different selectors
            file_input = None
            for selector in upload_selectors:
                try:
                    # Wait for the selector with a short timeout
                    await page.wait_for_selector(selector, state="attached", timeout=5000)
                    count = await page.locator(selector).count()
                    if count > 0:
                        file_input = page.locator(selector).first
                        logger.info(f"Found file input with selector: {selector}")
                        break
                except Exception:
                    logger.debug(f"Selector not found: {selector}")
            
            if not file_input:
                logger.warning("Could not find file input with standard selectors")
                raise ValueError("File input not found")
                
            # Set input files with diagnostic logging
            logger.info("Setting input files")
            await file_input.set_input_files(self.input_file_path)
            logger.info("Input files set successfully")
            
            # Wait a moment for the upload to process
            await asyncio.sleep(2)
            
            # Verify the upload was successful
            if await self._verify_file_uploaded(page):
                logger.info("File uploaded successfully using standard method")
                return True
            else:
                logger.warning("Standard file upload method may have failed")
                raise ValueError("Upload verification failed")
                
        except Exception as e:
            logger.warning(f"Standard upload method failed: {str(e)}")
            
            # Try alternative methods if first attempt failed
            if retry_count < 2:  # Limit alternative attempts
                return await self._upload_file_alternative(page, retry_count)
            else:
                raise Exception(f"All upload methods failed: {str(e)}")
    
    async def _upload_file_alternative(self, page, retry_count):
        """Try alternative upload methods."""
        retry_count += 1
        
        # Method 2: Try using drag-and-drop simulation
        try:
            logger.info(f"Upload method 2: Using JavaScript file upload simulation")
            
            # Create a JavaScript function to simulate the file upload
            result = await page.evaluate("""async () => {
                // Try to find the upload zone
                const uploadZones = [
                    document.querySelector('.upload-zone'),
                    document.querySelector('.dropzone'),
                    document.querySelector('[data-testid="upload-area"]'),
                    document.querySelector('.file-upload'),
                    // Add any additional selectors for upload areas
                ];
                
                // Find the first valid upload zone
                const uploadZone = uploadZones.find(zone => zone !== null);
                
                if (uploadZone) {
                    // Create a fake drag-drop event
                    const evt = new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    
                    // Dispatch the event on the upload zone
                    uploadZone.dispatchEvent(evt);
                    return { success: true, method: 'upload-zone-click' };
                }
                
                // Look for upload buttons as a fallback
                const uploadButtons = Array.from(document.querySelectorAll('button')).filter(btn => {
                    const text = btn.textContent.toLowerCase();
                    return text.includes('upload') || text.includes('choose') || text.includes('select');
                });
                
                if (uploadButtons.length > 0) {
                    uploadButtons[0].click();
                    return { success: true, method: 'button-click' };
                }
                
                return { success: false };
            }""")
            
            logger.info(f"JavaScript upload simulation result: {result}")
            
            # If JS method started the file selection dialog, handle it
            if result.get('success', False):
                try:
                    # Wait for the file chooser dialog
                    async with page.expect_file_chooser(timeout=10000) as fc_info:
                        # The dialog should already be triggered by the JS
                        await asyncio.sleep(1)
                    
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(self.input_file_path)
                    logger.info("File selected via file chooser dialog")
                    
                    # Wait a moment for upload to process
                    await asyncio.sleep(3)
                    
                    # Verify upload was successful
                    if await self._verify_file_uploaded(page):
                        logger.info("File uploaded successfully using file chooser")
                        return True
                    else:
                        logger.warning("File chooser upload method may have failed")
                except Exception as fc_error:
                    logger.warning(f"File chooser error: {str(fc_error)}")
            
            # Method 3: Try locating and clicking a specific upload button
            logger.info("Upload method 3: Finding and clicking upload button")
            
            # Look for upload buttons by text
            upload_button_texts = ["Upload", "Choose File", "Select Image", "Add Image"]
            for text in upload_button_texts:
                try:
                    # Use a case-insensitive regex pattern for the button name
                    pattern = re.compile(text, re.IGNORECASE)
                    button = page.get_by_role("button", name=pattern, exact=False)
                    count = await button.count()
                    
                    if count > 0 and await button.is_visible():
                        logger.info(f"Clicking '{text}' button to start processing")
                        await button.click()
                        # Only need to click one processing button
                        break
                except Exception as e:
                    logger.debug(f"No '{text}' button found or error clicking it: {str(e)}")
            
            # Wait for processing to complete and download button to appear
            # Try multiple selector approaches for the download button
            download_button_selectors = [
                "button:has-text('Download'):has(.sc-gueYoa)",
                "button.relative.cursor-pointer:has-text('Download')",
                "button:has(svg):has-text('Download')",
                "button:has(p.font-semibold:has-text('Download'))",
                "button.inline-flex:has-text('Download')",
                # Fallback to original selectors
                "button:has-text('Download')",
                "[data-testid='download-button']",
                ".download-button",
                "button.download",
                "a:has-text('Download')"
            ]
            
            # Look for any of the download button selectors
            download_button = None
            for selector in download_button_selectors:
                try:
                    logger.info(f"Waiting for download button with selector: {selector}")
                    await page.wait_for_selector(selector, state="visible", timeout=60000)
                    download_button = page.locator(selector).first
                    logger.info(f"Found download button with selector: {selector}")
                    break
                except Exception:
                    logger.debug(f"Download button not found with selector: {selector}")
            
            if not download_button:
                # Take a screenshot for debugging
                debug_screenshot = os.path.join(self.output_directory, "no_download_button.png")
                await page.screenshot(path=debug_screenshot)
                logger.error(f"No download button found. Screenshot saved at: {debug_screenshot}")
                raise Exception("Download button not found after processing")
            
            # Try to download the processed image
            # Try to download the processed image
            logger.info("Attempting to download processed image")
            
            # Check if button is disabled
            is_disabled = await download_button.is_disabled()
            if is_disabled:
                logger.warning("Download button appears to be disabled - possible limit reached")
                
                # Check specifically for limit messages when button is disabled
                page_text = await page.evaluate("() => document.body.innerText")
                debug_screenshot = os.path.join(self.output_directory, "disabled_button_check.png")
                await page.screenshot(path=debug_screenshot)
                logger.info(f"Saved screenshot for disabled button: {debug_screenshot}")
                
                # Look for limit-related text when button is disabled
                limit_phrases = [
                    "daily limit",
                    "hit your limit",
                    "reached your limit",
                    "try again tomorrow",
                    "try again later",
                    "too many requests",
                    "subscribe",
                    "premium",
                    "upgrade your plan",
                    "upgrade to pro"
                ]
                
                limit_detected = False
                for phrase in limit_phrases:
                    if phrase.lower() in page_text.lower():
                        logger.warning(f"Limit detected with disabled button: '{phrase}' found in page")
                        limit_detected = True
                        self.daily_limit_detected = True
                        break
                
                if limit_detected:
                    # Force VPN rotation when limit is detected
                    logger.info("Limit detected with disabled button - will force VPN rotation and retry")
                    
                    # Clean up resources before rotation
                    await context.close()
                    await browser.close()
                    
                    # Force IP rotation
                    await self._maybe_rotate_ip(force=True)
                    
                    # Wait longer before retrying after limit
                    wait_time = 15
                    logger.info(f"Waiting {wait_time} seconds after IP rotation before retrying...")
                    await asyncio.sleep(wait_time)
                    
                    # Throw exception to trigger retry with new IP
                    raise Exception("Hit usage limit - IP rotated and will retry with new connection")
                
                # If not explicitly a limit but button still disabled, wait and try again
                logger.warning("Download button is disabled but no limit detected, waiting before retry")
                await asyncio.sleep(10)
                
                # Check button status again
                is_disabled = await download_button.is_disabled()
                if is_disabled:
                    # Still disabled - capture more debugging info
                    logger.warning("Download button still disabled after waiting")
                    
                    # Take a DOM snapshot for debugging
                    dom_snapshot = await page.evaluate("""() => {
                        const downloadButtons = Array.from(document.querySelectorAll('button')).filter(btn => {
                            return btn.textContent.toLowerCase().includes('download');
                        });
                        
                        return {
                            buttonCount: downloadButtons.length,
                            buttonInfo: downloadButtons.map(btn => ({
                                text: btn.textContent,
                                disabled: btn.disabled,
                                visible: btn.offsetParent !== null,
                                classes: btn.className
                            })),
                            pageTitle: document.title,
                            visibleText: document.body.innerText.substring(0, 500) // First 500 chars
                        };
                    }""")
                    
                    logger.info(f"DOM snapshot for disabled button: {dom_snapshot}")
                    
                    # Try rotating IP after several attempts with disabled button
                    if retries >= self.max_retries - self.disabled_download_retries:
                        logger.warning("Multiple attempts with disabled button - will force IP rotation")
                        
                        # Clean up resources before rotation
                        await context.close()
                        await browser.close()
                        
                        # Force IP rotation as precaution
                        await self._maybe_rotate_ip(force=True)
                        
                        # Wait after rotation
                        await asyncio.sleep(10)
                        
                        # Throw exception to trigger retry with new IP
                        raise Exception("Disabled download button persists - rotating IP and retrying")
                    
                    # Will still try to click the button as last resort
                    logger.warning("Will attempt to click disabled button as last resort")
            # Setup download handler - increased timeout since we might have to wait
            download_timeout = 45000  # 45 seconds
            async with page.expect_download(timeout=download_timeout) as download_info:
                # Try to click the download button
                try:
                    logger.info("Attempting to click download button (force=True)")
                    await download_button.click(force=True)
                    logger.info("Clicked download button")
                except Exception as click_error:
                    logger.warning(f"Error clicking download button: {str(click_error)}")
                    
                    # Try JavaScript click as fallback with better error detection
                    logger.info("Trying JavaScript click with enhanced error detection")
                    js_result = await page.evaluate("""() => {
                        try {
                            // Find all buttons that might be download buttons
                            const buttons = Array.from(document.querySelectorAll('button'));
                            const downloadBtn = buttons.find(b => 
                                b.textContent.toLowerCase().includes('download') && 
                                !b.textContent.toLowerCase().includes('pro')
                            );
                            if (downloadBtn) {
                                console.log("Found download button via JavaScript:", downloadBtn.textContent);
                                
                                // Check for visible limit messaging around the button
                                const nearbyElements = [];
                                let el = downloadBtn.nextElementSibling;
                                while (el && nearbyElements.length < 5) {
                                    nearbyElements.push(el.textContent);
                                    el = el.nextElementSibling;
                                }
                                
                                el = downloadBtn.previousElementSibling;
                                while (el && nearbyElements.length < 10) {
                                    nearbyElements.push(el.textContent);
                                    el = el.previousElementSibling;
                                }
                                
                                const limitTexts = nearbyElements.filter(text => {
                                    if (!text) return false;
                                    const t = text.toLowerCase();
                                    return t.includes('limit') || t.includes('try again') || 
                                           t.includes('tomorrow') || t.includes('subscribe');
                                });
                                
                                // If limit texts found near button, report them
                                if (limitTexts.length > 0) {
                                    return { 
                                        clicked: false, 
                                        limitDetected: true,
                                        limitTexts
                                    };
                                }
                                
                                // Check button state
                                const wasDisabled = downloadBtn.disabled;
                                if (wasDisabled) {
                                    // Enable button if disabled
                                    downloadBtn.disabled = false;
                                    console.log("Enabled previously disabled button");
                                }
                                
                                // Click the button
                                downloadBtn.click();
                                return { clicked: true, wasDisabled };
                            } else {
                                console.log("No download button found via JavaScript");
                                return { clicked: false, reason: "Button not found" };
                            }
                        } catch (err) {
                            return { clicked: false, error: err.toString() };
                        }
                    }""")
                    
                    logger.info(f"JavaScript click result: {js_result}")
                    
                    # Check if limit was detected by JavaScript
                    if js_result.get('limitDetected', False):
                        limit_texts = js_result.get('limitTexts', [])
                        logger.warning(f"Limit detected via JavaScript near download button: {limit_texts}")
                        self.daily_limit_detected = True
                        
                        # Will let the download attempt continue but will likely fail
                        # The retry logic will handle the rotation after failure
                    
            # Wait for download with enhanced error handling
            try:
                # Get the download info
                download = await download_info.value
                
                # Verify that the download was successful
                failure = await download.failure()
                if failure:
                    error_msg = failure
                    logger.error(f"Download failed: {error_msg}")
                    
                    # Check if failure might be related to limits
                    if any(limit_term in str(error_msg).lower() for limit_term in ['limit', 'quota', 'exceeded', 'try again']):
                        logger.warning("Download failure appears related to usage limits")
                        self.daily_limit_detected = True
                        
                        # Force IP rotation for limit-related failures
                        await context.close()
                        await browser.close()
                        await self._maybe_rotate_ip(force=True)
                        await asyncio.sleep(10)  # Wait after rotation
                    
                    raise Exception(f"Download failed: {error_msg}")
                
                # Get the suggested filename and save path
                suggested_filename = download.suggested_filename()
                logger.info(f"Download completed with suggested filename: {suggested_filename}")
                
                # Get the binary data from the download
                temp_path = await download.path()
                with open(temp_path, 'rb') as f:
                    binary_data = f.read()
                
                # Process and save the image with correct format
                saved_path = await self._detect_image_format_and_save(binary_data, self.output_file_path)
                logger.info(f"Image processing completed successfully: {saved_path}")
            except Exception as download_error:
                logger.error(f"Error during download processing: {str(download_error)}")
                # Take a screenshot to help debugging
                try:
                    debug_screenshot = os.path.join(self.output_directory, "download_error.png")
                    await page.screenshot(path=debug_screenshot)
                    logger.info(f"Saved download error screenshot: {debug_screenshot}")
                except Exception:
                    pass
                # Re-raise the error to be caught by the outer exception handler
                raise download_error
            
            # Cleanup and return success
            await context.close()
            await browser.close()
            
            return saved_path
            
        except Exception as process_error:
            # Take a screenshot for debugging
            try:
                debug_screenshot = os.path.join(self.output_directory, f"error_{retries}.png")
                await page.screenshot(path=debug_screenshot)
                logger.info(f"Saved error screenshot: {debug_screenshot}")
            except Exception:
                pass
            
            # Re-raise the exception to be caught by the outer try/except
            raise process_error
        
    async def process_image(self, playwright: Playwright) -> str:
        """
        Process an image through dewatermark.ai with IP rotation and proper image saving.
        Returns the path to the saved processed image.
        """
        retries = 0
        last_error = None
        max_retries = 4  # Increased from 3 to 4 for more resilience
        
        # Ensure VPN is connected and check if rotation is needed before processing
        logger.info("Verifying VPN connection before starting processing")
        vpn_connected = ImageProcessor.vpn_manager.verify_connection_status()
        
        if not vpn_connected:
            logger.warning("VPN not connected, connecting now...")
            connection_attempts = 0
            max_connection_attempts = 3
            
            while not vpn_connected and connection_attempts < max_connection_attempts:
                logger.info(f"VPN connection attempt {connection_attempts + 1}/{max_connection_attempts}")
                
                # Try to connect using a specific location from the rotation
                location = ImageProcessor.vpn_manager.get_next_location()
                if ImageProcessor.vpn_manager.connect(location):
                    logger.info(f"Successfully connected to VPN location: {location}")
                    vpn_connected = True
                    break
                
                connection_attempts += 1
                if connection_attempts < max_connection_attempts:
                    logger.warning(f"Connection attempt {connection_attempts} failed, retrying after short wait...")
                    await asyncio.sleep(2)
            
            if not vpn_connected:
                logger.warning(f"Failed to connect VPN after {max_connection_attempts} attempts, will attempt processing anyway")
        else:
            logger.info("VPN is already connected and verified")
        
        # Check and rotate IP if needed before processing
        logger.info("Checking if IP rotation is needed before processing")
        await self._maybe_rotate_ip()
        
        while retries < self.max_retries:
            try:
                logger.info(f"Processing image: {self.input_file_path} (Attempt {retries + 1}/{self.max_retries})")
                
                # Launch browser with additional options for stability
                browser = await playwright.chromium.launch(
                    headless=False,
                    args=[
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--disable-blink-features=AutomationControlled",  # Help avoid detection
                        "--no-sandbox",
                        "--disable-setuid-sandbox"
                    ]
                )
                
                # Configure context with additional settings for downloads and viewport
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    accept_downloads=True,
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
                    permissions=["clipboard-read", "clipboard-write"]
                )
                
                # Set additional HTTP headers to appear more like a regular browser
                await context.set_extra_http_headers({
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "keep-alive",
                    "DNT": "1",
                    "Upgrade-Insecure-Requests": "1"
                })
                
                # Create page with appropriate timeout
                page = await context.new_page()
                page.set_default_timeout(30000)  # 30 second timeout
                
                try:
                    # Navigate to the dewatermark.ai site
                    logger.info("Navigating to dewatermark.ai")
                    await page.goto("https://dewatermark.ai/", wait_until="networkidle")
                    
                    # Check for daily limit on initial page load
                    page_text = await page.evaluate("() => document.body.innerText")
                    daily_limit_phrases = [
                        "daily limit", 
                        "You’ve hit your daily limit"
                        "hit your limit", 
                        "reached your limit",
                        "try again tomorrow",
                        "try again later",
                        "too many requests"
                    ]
                    
                    for phrase in daily_limit_phrases:
                        if phrase.lower() in page_text.lower():
                            logger.warning(f"Daily limit detected on page load: '{phrase}' found in page")
                            self.daily_limit_detected = True
                            
                            # Take a screenshot for evidence
                            screenshot_path = os.path.join(self.output_directory, "daily_limit_initial.png")
                            await page.screenshot(path=screenshot_path)
                            logger.info(f"Daily limit screenshot saved to: {screenshot_path}")
                            
                            # Raise an exception to trigger retry with IP rotation
                            raise Exception(f"Daily limit detected: {phrase}")
                    
                    # Take a screenshot for debugging
                    debug_screenshot = os.path.join(self.output_directory, "initial_site.png")
                    await page.screenshot(path=debug_screenshot)
                    logger.info(f"Saved initial site screenshot: {debug_screenshot}")
                    
                    # Upload the image file using our enhanced upload mechanism
                    logger.info("Starting file upload process")
                    upload_success = await self._upload_file(page)
                    
                    if not upload_success:
                        logger.error("File upload failed after multiple attempts")
                        raise Exception("Failed to upload file to dewatermark.ai")
                    
                    # Wait for processing to complete
                    logger.info("File uploaded, waiting for processing to complete")
                    
                    # Click any processing/start buttons if needed
                    processing_button_texts = [
                        "Start",
                        "Process",
                        "Remove Watermark",
                        "Dewatermark",
                        "Continue"
                    ]
                    
                    for text in processing_button_texts:
                        try:
                            # Check if button exists and is visible
                            button = page.get_by_role("button", name=text, exact=False)
                            count = await button.count()
                            
                            if count > 0 and await button.is_visible():
                                logger.info(f"Clicking '{text}' button to start processing")
                                await button.click()
                                # Only need to click one processing button
                                break
                        except Exception as e:
                            logger.debug(f"No '{text}' button found or error clicking it: {str(e)}")
                    
                    # Wait for processing to complete and download button to appear
                    # Try multiple selector approaches for the download button
                    download_button_selectors = [
                        "button:has-text('Download'):has(.sc-gueYoa)",
                        "button.relative.cursor-pointer:has-text('Download')",
                        "button:has(svg):has-text('Download')",
                        "button:has(p.font-semibold:has-text('Download'))",
                        "button.inline-flex:has-text('Download')",
                        # Fallback to original selectors
                        "button:has-text('Download')",
                        "[data-testid='download-button']",
                        ".download-button",
                        "button.download",
                        "a:has-text('Download')"
                    ]
                    
                    # Look for any of the download button selectors with a longer timeout
                    download_button = None
                    download_button_timeout = 90000  # 90 seconds for processing to complete
                    for selector in download_button_selectors:
                        try:
                            logger.info(f"Waiting for download button with selector: {selector}")
                            await page.wait_for_selector(selector, state="visible", timeout=download_button_timeout)
                            download_button = page.locator(selector).first
                            logger.info(f"Found download button with selector: {selector}")
                            break
                        except Exception:
                            logger.debug(f"Download button not found with selector: {selector}")
                    
                    if not download_button:
                        # Take a screenshot for debugging
                        debug_screenshot = os.path.join(self.output_directory, "no_download_button.png")
                        await page.screenshot(path=debug_screenshot)
                        logger.error(f"No download button found. Screenshot saved at: {debug_screenshot}")
                        
                        # Try to extract direct image source as fallback
                        logger.info("Attempting to extract processed image directly since download button not found")
                        img_src = await page.evaluate("""
                        () => {
                            // Look for the result image - check different possible elements
                            const resultImg = document.querySelector('.result-image img') || 
                                             document.querySelector('.processed-image') ||
                                             document.querySelector('#result-img');
                            if (resultImg && resultImg.src) {
                                return resultImg.src;
                            }
                            
                            // If no specific element found, try to find the largest image
                            const images = Array.from(document.querySelectorAll('img'));
                            let largestImg = null;
                            let maxArea = 0;
                            
                            for (const img of images) {
                                const area = img.width * img.height;
                                if (area > maxArea && img.src && 
                                    !img.src.includes('logo') && 
                                    !img.src.includes('icon')) {
                                    maxArea = area;
                                    largestImg = img;
                                }
                            }
                            
                            return largestImg ? largestImg.src : null;
                        }
                        """)
                        
                        if img_src:
                            logger.info(f"Found image source: {img_src[:50]}...")
                            # Save a screenshot as fallback
                            screenshot_path = os.path.join(self.output_directory, f"screenshot_result_{os.path.basename(self.input_file_path)}")
                            await page.screenshot(path=screenshot_path)
                            logger.info(f"Saved result screenshot: {screenshot_path}")
                            
                            # Clean up resources before returning
                            await context.close()
                            await browser.close()
                            return screenshot_path
                        else:
                            raise Exception("Download button not found after processing and no direct image found")
                    
                    # Try to download the processed image
                    logger.info("Attempting to download processed image")
                    
                    # Check if button is disabled
                    is_disabled = await download_button.is_disabled()
                    if is_disabled:
                        logger.warning("Download button appears to be disabled - possible limit reached")
                        
                        # Check specifically for limit messages when button is disabled
                        page_text = await page.evaluate("() => document.body.innerText")
                        debug_screenshot = os.path.join(self.output_directory, "disabled_button_check.png")
                        await page.screenshot(path=debug_screenshot)
                        logger.info(f"Saved screenshot for disabled button: {debug_screenshot}")
                        
                        # Look for limit-related text when button is disabled
                        limit_phrases = [
                            "daily limit",
                            "hit your limit",
                            "reached your limit",
                            "try again tomorrow",
                            "try again later",
                            "too many requests",
                            "subscribe",
                            "premium",
                            "upgrade your plan",
                            "upgrade to pro"
                        ]
                        
                        limit_detected = False
                        for phrase in limit_phrases:
                            if phrase.lower() in page_text.lower():
                                logger.warning(f"Limit detected with disabled button: '{phrase}' found in page")
                                limit_detected = True
                                self.daily_limit_detected = True
                                break
                        
                        if limit_detected:
                            # Force VPN rotation when limit is detected
                            logger.info("Limit detected with disabled button - will force VPN rotation and retry")
                            
                            # Clean up resources before rotation
                            await context.close()
                            await browser.close()
                            
                            # Force IP rotation
                            await self._maybe_rotate_ip(force=True)
                            
                            # Wait longer before retrying after limit
                            wait_time = 15
                            logger.info(f"Waiting {wait_time} seconds after IP rotation before retrying...")
                            await asyncio.sleep(wait_time)
                            
                            # Throw exception to trigger retry with new IP
                            raise Exception("Hit usage limit - IP rotated and will retry with new connection")
                        
                        # Try enabling and clicking the button with JavaScript even if disabled
                        logger.info("Attempting to use JavaScript to enable disabled button")
                        js_click_result = await page.evaluate("""
                        () => {
                            const buttons = Array.from(document.querySelectorAll('button'));
                            const downloadBtn = buttons.find(b => 
                                b.textContent.toLowerCase().includes('download') && 
                                !b.textContent.toLowerCase().includes('pro')
                            );
                            if (downloadBtn) {
                                console.log("Found download button via JavaScript");
                                // Enable button if disabled
                                if (downloadBtn.disabled) {
                                    downloadBtn.disabled = false;
                                    console.log("Enabled previously disabled button");
                                }
                                downloadBtn.click();
                                return { clicked: true };
                            }
                            return { clicked: false, reason: "Button not found" };
                        }
                        """)
                        
                        logger.info(f"JavaScript click result: {js_click_result}")
                    
                    # Setup download handler with increased timeout
                    download_timeout = 60000  # 60 seconds
                    async with page.expect_download(timeout=download_timeout) as download_info:
                        # Try to click the download button (force=True to bypass disabled state)
                        try:
                            logger.info("Clicking download button (force=True)")
                            await download_button.click(force=True)
                        except Exception as click_error:
                            logger.warning(f"Normal click failed: {click_error}, but continuing with download handler")
                    
                    # Wait for download with enhanced error handling
                    try:
                        # Get the download info
                        download = await download_info.value
                        
                        # Verify that the download was successful
                        failure = await download.failure()
                        if failure:
                            error_msg = failure
                            logger.error(f"Download failed: {error_msg}")
                            
                            # Check if failure might be related to limits
                            if any(limit_term in str(error_msg).lower() for limit_term in ['limit', 'quota', 'exceeded', 'try again']):
                                logger.warning("Download failure appears related to usage limits")
                                self.daily_limit_detected = True
                                
                                # Force IP rotation for limit-related failures
                                await context.close()
                                await browser.close()
                                await self._maybe_rotate_ip(force=True)
                                await asyncio.sleep(10)  # Wait after rotation
                            
                            # Take a screenshot of result as fallback
                            screenshot_path = os.path.join(self.output_directory, f"fallback_{os.path.basename(self.input_file_path)}")
                            await page.screenshot(path=screenshot_path)
                            logger.info(f"Saved fallback screenshot: {screenshot_path}")
                            
                            # Try to find images on the page for potential direct extraction
                            img_src = await page.evaluate("""
                            () => {
                                // Find the largest image that might be our result
                                const images = Array.from(document.querySelectorAll('img'));
                                let largestImg = null;
                                let maxArea = 0;
                                
                                for (const img of images) {
                                    const area = img.width * img.height;
                                    if (area > maxArea && img.src && 
                                        !img.src.includes('logo') && 
                                        !img.src.includes('icon')) {
                                        maxArea = area;
                                        largestImg = img;
                                    }
                                }
                                
                                return largestImg ? largestImg.src : null;
                            }
                            """)
                            
                            if img_src:
                                logger.info("Found potential result image on page")
                                # Use the screenshot as our processed result for now
                                await context.close()
                                await browser.close()
                                return screenshot_path
                            
                            raise Exception(f"Download failed: {error_msg}")
                        
                        # Get the suggested filename and save path
                        suggested_filename = download.suggested_filename()
                        logger.info(f"Download completed with suggested filename: {suggested_filename}")
                        
                        # Get the binary data from the download
                        temp_path = await download.path()
                        with open(temp_path, 'rb') as f:
                            binary_data = f.read()
                        
                        # Process and save the image with correct format
                        saved_path = await self._detect_image_format_and_save(binary_data, self.output_file_path)
                        logger.info(f"Image processing completed successfully: {saved_path}")
                        
                        # Clean up resources
                        await context.close()
                        await browser.close()
                        
                        return saved_path
                    
                    except Exception as download_error:
                        logger.error(f"Error during download processing: {str(download_error)}")
                        
                        # Try fallback - take a screenshot of what we have
                        try:
                            fallback_path = os.path.join(self.output_directory, f"fallback_{os.path.basename(self.input_file_path)}")
                            await page.screenshot(path=fallback_path)
                            logger.info(f"Saved fallback screenshot after download error: {fallback_path}")
                            
                            # Clean up and return the fallback screenshot
                            await context.close()
                            await browser.close()
                            return fallback_path
                        except Exception:
                            # Re-raise the original error
                            raise download_error
                
                except Exception as process_error:
                    # Take a screenshot for debugging
                    try:
                        debug_screenshot = os.path.join(self.output_directory, f"error_{retries}.png")
                        await page.screenshot(path=debug_screenshot)
                        logger.info(f"Saved error screenshot: {debug_screenshot}")
                    except Exception:
                        pass
                    
                    # Clean up resources
                    await context.close()
                    await browser.close()
                    
                    # Re-raise the exception to be caught by the outer try/except
                    raise process_error
                
            except Exception as e:
                retries += 1
                last_error = e
                logger.error(f"Error during attempt {retries}/{self.max_retries}: {str(e)}")
                
                # Check if the error suggests a rate limit or service issue
                error_lower = str(e).lower()
                rate_limit_indicators = [
                    "limit", "quota", "exceeded", "429", "too many", 
                    "try again", "tomorrow", "later", "daily"
                ]
                
                if any(indicator in error_lower for indicator in rate_limit_indicators):
                    logger.warning("Detected rate limit or service issue from error message")
                    
                    # If this is a daily limit or persistent issue, force reconnect
                    force_reconnect = "tomorrow" in error_lower or "daily" in error_lower or retries > 1
                    
                    # Try to rotate IP
                    if await self._maybe_rotate_ip(force=True, force_reconnect=force_reconnect):
                        logger.info("Successfully rotated IP after error detection")
                        # Wait longer before retry
                        wait_time = 15 if retries == 1 else 25
                        logger.info(f"Waiting {wait_time} seconds before retry...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning("Failed to rotate IP after error. Waiting longer...")
                        # Longer wait if rotation failed
                        wait_time = 30 if retries == 1 else 45
                        logger.info(f"Waiting {wait_time} seconds before retry...")
                        await asyncio.sleep(wait_time)
                else:
                    # For non-rate-limit errors, wait progressively longer
                    wait_time = 5 * retries
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                
                # If we've reached max retries, log and return None
                if retries >= self.max_retries:
                    logger.error(f"Max retries ({self.max_retries}) reached. Last error: {str(last_error)}")
                    return None
                
        # This would be unreachable as the loop will exit via return or exception
        return None

# Example usage:
# async def main():
#     async with async_playwright() as playwright:
#         processor = ImageProcessor('media/input_image.jpeg', 'output_directory')
#         result_path = await processor.process_image(playwright)
#         print(f"Processed image saved to: {result_path}")
#
# # Run with asyncio
# import asyncio
# asyncio.run(main())
