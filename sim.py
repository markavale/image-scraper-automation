import os
import asyncio
from playwright.async_api import async_playwright, Error as PlaywrightError, TimeoutError
from core.downloader import ImageProcessor
from helpers.windscribe_helpers import WindscribeManager
import subprocess

class ImageManager:
    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.windscribe_manager = WindscribeManager()

    def get_images(self):
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        image_files = []
        for filename in os.listdir(self.folder_path):
            _, ext = os.path.splitext(filename)
            if ext.lower() in valid_extensions:
                image_files.append(os.path.join(self.folder_path, filename))
        return image_files

    async def download_image(self, image_path, idx, output_folder, max_retries=3):
        try:
            async with async_playwright() as playwright:
                output_path = os.path.join(output_folder, f'image_{idx}.jpg')
                processor = ImageProcessor(image_path, output_path)
                retries = 0
                while retries < max_retries:
                    try:
                        await processor.process_image(playwright)
                        print(f"Downloaded image {idx + 1} to {output_path}")
                        break
                    except PlaywrightError as e:
                        if "net::ERR_NETWORK_CHANGED" in str(e):
                            print(f"Network error encountered: {e}. Retrying...")
                            retries += 1
                            await asyncio.sleep(2)  # Wait before retrying
                        elif isinstance(e, TimeoutError):
                            print(f"Timeout error encountered: {e}. Retrying...")
                            await self.windscribe_manager.reboot()
                            retries += 1
                            await asyncio.sleep(2)  # Wait before retrying
                        else:
                            print("Raising error!!!!")
                            raise e
        except Exception as e:
            print(f"Error downloading image {idx + 1}: {e}")
            raise e


class ImageDownloaderApp:
    def __init__(self, bib_numbers):
        self.bib_numbers = bib_numbers
        self.windscribe_manager = WindscribeManager()

    async def run(self):
        # subprocess.run(['windscribe-cli', 'connect'], check=True)
        await self.windscribe_manager.aconnect()
        for bib_number in self.bib_numbers:
            folder_path = f"media/{bib_number}"
            output_folder = f"downloaded_images/{bib_number}"
            os.makedirs(output_folder, exist_ok=True)

            image_manager = ImageManager(folder_path)
            images = image_manager.get_images()

            for idx, image in enumerate(images):
                try:
                    if (idx + 1) % 4 == 0:
                        await self.windscribe_manager.reboot()
                    await image_manager.download_image(image, idx, output_folder)
                except Exception as e:
                    print("Exception", e)
                    await self.windscribe_manager.reboot()
                    await image_manager.download_image(image, idx, output_folder)


async def main():
    BIB_NUMBERS = ["5564"]#["11420", "11421", "11422", "10768"]
    print("Starting...")
    app = ImageDownloaderApp(BIB_NUMBERS)
    await app.run()



if __name__ == "__main__":
    asyncio.run(main())