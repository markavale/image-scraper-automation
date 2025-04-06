import requests
import base64
import os

url = 'https://app.imggen.ai/v1/remove-watermark'
api_key = '907e7534-8a09-4104-80b6-72464ae90e0a'
image_path = 'media/5564/image_0.jpeg'

# Check if the file exists and is an image
if not os.path.isfile(image_path):
    print("File does not exist.")
elif not image_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
    print("File is not a valid image type.")
else:
    headers = {
        'X-IMGGEN-KEY': api_key
    }

    # Open the image file in binary mode
    with open(image_path, 'rb') as image_file:
        files = {
            'image[]': image_file
        }

        # Make the POST request
        response = requests.post(url, headers=headers, files=files)

    # Check the response
    if response.status_code == 200:
        response_data = response.json()
        if response_data.get("success"):
            print(response_data.get("message"))

            # Decode and save each image
            for i, image_data in enumerate(response_data.get("images", [])):
                image_bytes = base64.b64decode(image_data)
                output_path = f'output_image_{i}.jpg'
                with open(output_path, 'wb') as output_file:
                    output_file.write(image_bytes)
                print(f"Image saved as {output_path}")
        else:
            print("Failed to remove watermark:", response_data.get("message"))
    else:
        print(f"Failed to remove watermark. Status code: {response.status_code}")
        print(response.text)