# /// script
# dependencies = [
#   "pillow",
# ]
# ///

import os
from PIL import Image

def process_icon():
    # Source image path (new 3D orange icon on black background)
    src_path = r"C:\Users\gayad\.gemini\antigravity-ide\brain\7577274b-95c1-426b-923c-5ecf1d8fb03f\pulsedag_3d_orange_icon_1780515716560.png"
    
    if not os.path.exists(src_path):
        print(f"Error: Source image not found at {src_path}")
        return

    img = Image.open(src_path).convert("RGBA")
    datas = img.getdata()
    new_data = []
    
    for item in datas:
        r, g, b, a = item
        # Use maximum channel value as brightness/intensity to detect black
        v = max(r, g, b)
        
        # If it is black, make it transparent
        if v < 8:
            new_data.append((0, 0, 0, 0))
        # If it is in the transition zone, map alpha proportionally
        elif v < 40:
            factor = (v - 8) / (40 - 8)
            new_data.append((r, g, b, int(255 * factor)))
        else:
            new_data.append((r, g, b, 255))
            
    img.putdata(new_data)
    
    # Find the bounding box of non-transparent pixels to crop it tightly
    alpha = img.split()[3]
    bbox = alpha.getbbox()
    
    if bbox:
        # Crop to bounding box
        img = img.crop(bbox)
        # Make it square and add a minimal 2% padding around the logo (less border)
        w, h = img.size
        max_dim = max(w, h)
        padding = int(max_dim * 0.02)
        padded_dim = max_dim + padding * 2
        
        square_img = Image.new("RGBA", (padded_dim, padded_dim), (0, 0, 0, 0))
        # Paste centered
        offset_x = (padded_dim - w) // 2
        offset_y = (padded_dim - h) // 2
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
