# /// script
# dependencies = [
#   "pillow",
# ]
# ///

import os
import math
from PIL import Image

def process_icon():
    # Source image path (new flat vector icon)
    src_path = r"C:\Users\gayad\.gemini\antigravity-ide\brain\7577274b-95c1-426b-923c-5ecf1d8fb03f\pulsedag_icon_flat_1780515317613.png"
    
    if not os.path.exists(src_path):
        print(f"Error: Source image not found at {src_path}")
        return

    img = Image.open(src_path).convert("RGBA")
    
    # Pre-crop the image to remove the corner artifacts (decorative lines)
    # The logo is centered within (163, 163) and (861, 861) on the 1024x1024 canvas.
    img = img.crop((160, 160, 864, 864))
    
    # The background is a uniform dark grey, around (49, 49, 49).
    # We remove this background and handle transparency mapping to avoid jaggy edges.
    bg_color = (49, 49, 49)
    datas = img.getdata()
    new_data = []
    
    for item in datas:
        r, g, b, a = item
        # Compute Euclidean distance to the background color
        dist = math.sqrt((r - bg_color[0])**2 + (g - bg_color[1])**2 + (b - bg_color[2])**2)
        
        # If it is very close to the background color, make it fully transparent
        if dist < 12:
            new_data.append((0, 0, 0, 0))
        # If it is in the transition zone, map alpha proportionally
        elif dist < 45:
            factor = (dist - 12) / (45 - 12)
            # Maintain the color but scale down the alpha channel
            new_data.append((r, g, b, int(255 * factor)))
        else:
            new_data.append((r, g, b, 255))
            
    img.putdata(new_data)
    
    # Find the bounding box of non-transparent pixels to crop it nicely
    alpha = img.split()[3]
    bbox = alpha.getbbox()
    
    if bbox:
        # Crop to bounding box
        img = img.crop(bbox)
        # Make it square by adding transparent padding
        w, h = img.size
        max_dim = max(w, h)
        square_img = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
        # Paste centered
        offset_x = (max_dim - w) // 2
        offset_y = (max_dim - h) // 2
        square_img.paste(img, (offset_x, offset_y))
        img = square_img
    
    # Output directory
    out_dir = r"c:\Users\gayad\dev\EAG3\MultiAgent-DAG\extension\icons"
    os.makedirs(out_dir, exist_ok=True)
    
    # Save standard sizes: 128x128, 48x48, 16x16
    for size in (16, 48, 128):
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        out_path = os.path.join(out_dir, f"icon{size}.png")
        resized.save(out_path)
        print(f"Saved {out_path}")

if __name__ == "__main__":
    process_icon()
