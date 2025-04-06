import json 
import base64

def get_json():
    with open('data.json', 'r') as file:
        return json.load(file)['edited_image']['image']
    
image_base64 = get_json()



def save_base64_image(base64_data, output_path):
    # Decode the base64 data
    image_data = base64.b64decode(base64_data)
    
    # Write the binary data to a file
    with open(output_path, 'wb') as image_file:
        image_file.write(image_data)

# Example usage
base64_image_data = image_base64  # Your base64 string here
output_image_path = "output_image.jpeg"
save_base64_image(base64_image_data, output_image_path)