import os
import math
from PIL import Image, ImageDraw

def get_gradient_color(t):
    # t goes from 0.0 to 1.0. We map it to:
    # 0.0 -> Indigo (99, 102, 241)
    # 0.5 -> Violet (168, 85, 247)
    # 1.0 -> Neon Green (52, 245, 168)
    if t < 0.5:
        factor = t / 0.5
        r = int(99 + (168 - 99) * factor)
        g = int(102 + (85 - 102) * factor)
        b = int(241 + (247 - 241) * factor)
    else:
        factor = (t - 0.5) / 0.5
        r = int(168 + (52 - 168) * factor)
        g = int(85 + (245 - 85) * factor)
        b = int(247 + (168 - 247) * factor)
    return (r, g, b)

def draw_glow_line(draw, points, width, alpha, color_func):
    # Draw the line segment by segment to achieve a smooth color gradient
    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i+1]
        t = i / (len(points) - 1)
        r, g, b = color_func(t)
        draw.line([p1, p2], fill=(r, g, b, alpha), width=width, joint="curve")

def make_vector_icon(size):
    # Render at 4x supersampling for crisp edges
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 1. Generate points for a smooth pulse/ECG curve
    raw_points = []
    num_steps = 120
    for i in range(num_steps + 1):
        x_pct = 0.1 + 0.8 * (i / num_steps)
        x = x_pct * s
        
        # Base height is around 56% down
        y_pct = 0.56
        
        # Add peak/valley offsets using gaussian bells
        # First small dip/peak before the main pulse
        dist_pre = x_pct - 0.36
        y_pct += 0.05 * math.exp(- (dist_pre / 0.04)**2)
        
        # Main sharp upward peak
        dist_peak = x_pct - 0.46
        y_pct -= 0.38 * math.exp(- (dist_peak / 0.04)**2)
        
        # Main sharp downward valley
        dist_valley = x_pct - 0.54
        y_pct += 0.28 * math.exp(- (dist_valley / 0.04)**2)
        
        # Secondary recovery peak
        dist_post = x_pct - 0.64
        y_pct -= 0.12 * math.exp(- (dist_post / 0.04)**2)
        
        y = y_pct * s
        raw_points.append((x, y))
        
    # 2. Draw the pulse line with multiple layers for a glowing neon neon effect
    draw_glow_line(draw, raw_points, int(14 * scale), 20, get_gradient_color)
    draw_glow_line(draw, raw_points, int(8 * scale), 50, get_gradient_color)
    draw_glow_line(draw, raw_points, int(4 * scale), 120, get_gradient_color)
    draw_glow_line(draw, raw_points, int(2 * scale), 255, get_gradient_color)
    
    # 3. Define the three DAG nodes (Left, Top/Middle, Right)
    # Positioning them exactly on the curve peaks/valleys
    nodes = [
        (0.28 * s, 0.56 * s),
        (0.46 * s, 0.18 * s),
        (0.64 * s, 0.44 * s)
    ]
    
    # 4. Draw DAG directed connection lines (edges) with clean glows
    edge_width = int(2 * scale)
    for i in range(len(nodes) - 1):
        # Glow edge
        draw.line([nodes[i], nodes[i+1]], fill=(255, 255, 255, 45), width=edge_width * 2)
        # Core edge
        draw.line([nodes[i], nodes[i+1]], fill=(255, 255, 255, 180), width=edge_width)
        
    # 5. Draw the glowing nodes
    r_outer = 12 * scale
    r_inner = 6.5 * scale
    r_core = 3 * scale
    
    for (nx, ny) in nodes:
        # Purple glow background for node
        draw.ellipse([nx - r_outer, ny - r_outer, nx + r_outer, ny + r_outer], fill=(168, 85, 247, 50))
        # White outer circle
        draw.ellipse([nx - r_inner, ny - r_inner, nx + r_inner, ny + r_inner], fill=(255, 255, 255, 180))
        # Solid white core
        draw.ellipse([nx - r_core, ny - r_core, nx + r_core, ny + r_core], fill=(255, 255, 255, 255))
        
    # Downsample using LANCZOS to get perfect anti-aliased output
    return img.resize((size, size), Image.Resampling.LANCZOS)

def main():
    out_dir = r"c:\Users\gayad\dev\EAG3\MultiAgent-DAG\extension\icons"
    os.makedirs(out_dir, exist_ok=True)
    
    for size in (16, 48, 128):
        img = make_vector_icon(size)
        out_path = os.path.join(out_dir, f"icon{size}.png")
        img.save(out_path)
        print(f"Generated clean transparent {out_path}")

if __name__ == "__main__":
    main()
