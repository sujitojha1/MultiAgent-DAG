# /// script
# dependencies = [
#   "pillow",
# ]
# ///

import os
from PIL import Image, ImageChops

def process_icon():
    # Source image path
    src_path = r"C:\Users\gayad\.gemini\antigravity-ide\brain\179aaa39-92f7-49b2-872d-42f3eb798d9a\pulsedag_3d_icon_1780513879702.png"
    
    if not os.path.exists(src_path):
        print(f"Error: Source image not found at {src_path}")
        return

    img = Image.open(src_path).convert("RGBA")
    
    # Let's find the bounding box of non-black pixels to crop it nicely.
    # Convert to grayscale first to easily find threshold
    gray = img.convert("L")
    # Threshold to find non-black pixels (brightness > 15)
    bw = gray.point(lambda x: 255 if x > 15 else 0)
    bbox = bw.getbbox()
    
    if bbox:
        # Crop to bounding box
        img = img.crop(bbox)
        # Make it square by adding padding
        w, h = img.size
        max_dim = max(w, h)
        square_img = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
        # Paste centered
        offset_x = (max_dim - w) // 2
        offset_y = (max_dim - h) // 2
        square_img.paste(img, (offset_x, offset_y))
        img = square_img
    
    # Process transparency
    # For every pixel, if it's very dark, make it transparent.
    # To avoid jaggy edges, we scale alpha based on pixel brightness for dark pixels.
    datas = img.getdata()
    new_data = []
    for item in datas:
        r, g, b, a = item
        # Brightness estimate
        brightness = (r + g + b) / 3.0
        
        # If it's very dark, make it transparent
        if brightness < 12:
            new_data.append((0, 0, 0, 0))
        elif brightness < 45:
            # Smoothly transition alpha for dark edges
            factor = (brightness - 12) / (45 - 12)
            new_data.append((r, g, b, int(255 * factor)))
        else:
            new_data.append((r, g, b, 255))
            
    img.putdata(new_data)
    
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
