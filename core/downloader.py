from playwright.async_api import Playwright

class ImageProcessor:
    def __init__(self, input_file_path: str, output_file_path: str):
        self.input_file_path = input_file_path
        self.output_file_path = output_file_path

    async def process_image(self, playwright: Playwright) -> None:
        try:
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto("https://dewatermark.ai/upload")
            
            # Upload the image file
            await page.set_input_files('input[type="file"][accept="image/png, image/jpeg"]', self.input_file_path)
            
            # Click the button to start processing
            await page.get_by_role("button", name="Logo header Batch Process").click()
            
            async with page.expect_download() as download_info:
                await page.get_by_role("button", name="Download", exact=True).click()

            if download_info:
                print(download_info, "download here....")
            download = await download_info.value
            await download.save_as(self.output_file_path)

            # Close the context and browser
            await context.close()
            await browser.close()
        except Exception as e:
            print("Exception at process_image", e)
            raise e

# # Usage
# with sync_playwright() as playwright:
#     processor = ImageProcessor('media/5564/image_0.jpeg', 'image_0.jpg')
#     processor.process_image(playwright)