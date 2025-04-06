import os
import asyncio
from playwright.async_api import async_playwright, Error as PlaywrightError, TimeoutError
from core.downloader import ImageProcessor
from helpers.windscribe_helpers import Windscribe
import subprocess
import random

class WindscribeManager:
    _instance = None
    connected_states = []

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(WindscribeManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.vpn = Windscribe('servers.txt', 'markavale', '@Linux121598')

    async def reboot(self):
        status = self.get_status()
        state = status.get('Connect state', status.get('*Connect state'))
        if state in ["Disconnected", "Disconnecting"]:
            await self.connect()
        else:
            subprocess.run(['windscribe-cli', 'disconnect'], check=True)
            await self.connect()
        print("Windscribe has been rebooted.")

    def parse_status(self, output):
        output_str = output.decode('utf-8').strip()
        lines = output_str.split('\n')
        status_dict = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                status_dict[key.strip()] = value.strip()
        return status_dict

    def get_status(self):
        response = subprocess.run(['windscribe-cli', 'status'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return self.parse_status(response.stdout)

    async def connect(self):
        status = self.get_status()
        state = status.get('Connect state', status.get('*Connect state'))
        while state in ["Disconnected", "Disconnecting"]:
            self.vpn.connect(rand=True)
            await asyncio.sleep(random.uniform(0.5, 2.5))
            status = self.get_status()
            state = status.get('Connect state', status.get('*Connect state'))
            print(state, "status here...")
        self.connected_states.append(state)


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
                            raise e
        except Exception as e:
            print(f"Error downloading image {idx + 1}: {e}")
            raise e


class ImageDownloaderApp:
    def __init__(self, bib_numbers):
        self.bib_numbers = bib_numbers
        self.windscribe_manager = WindscribeManager()

    async def run(self):
        # await self.windscribe_manager.reboot()
        subprocess.run(['windscribe-cli', 'connect'], check=True)
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
    BIB_NUMBERS = ["11420", "11421", "11422", "10768"]
    print("Starting...")
    app = ImageDownloaderApp(BIB_NUMBERS)
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())