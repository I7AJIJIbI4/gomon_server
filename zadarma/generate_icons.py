#!/usr/bin/env python3
"""
Generate stylized gold-on-black PNG icons (260x260) for ALL WLaunch CRM services.
BOLD thick-line art style — luxury cosmetic brand aesthetic.
63 icons total: 5 categories + 58 services.
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont

# --- Config ---
SIZE = 260
BG = "#111111"
GOLD = "#D4AF37"      # primary — brighter gold
GOLD2 = "#C9A96E"     # secondary — softer accent
LW = 3                # default line width (was 1)
LW2 = 2               # secondary line width
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wl_icons")
os.makedirs(OUT_DIR, exist_ok=True)

# Font
def get_font(size):
    for path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()

FONT_LABEL = get_font(15)
FONT_SMALL = get_font(12)

CX, CY = SIZE // 2, SIZE // 2 - 18  # center shifted up for label


# --- Drawing helpers ---

def new_icon():
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)
    return img, draw


def draw_label(draw, text, y_start=212):
    """Draw 1-2 line gold label centered at bottom."""
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=FONT_LABEL)
        if bbox[2] - bbox[0] > SIZE - 16:
            if current:
                lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)
    if len(lines) > 2:
        lines = [" ".join(lines[:len(lines)//2]), " ".join(lines[len(lines)//2:])]
    for i, line in enumerate(lines):
        font = FONT_LABEL if len(lines) == 1 else FONT_SMALL
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (SIZE - tw) // 2
        y = y_start + i * 17
        draw.text((x, y), line, fill=GOLD, font=font)


def save_icon(img, filename):
    path = os.path.join(OUT_DIR, filename)
    img.save(path, "PNG")
    print(f"  -> {path}")


# ===== DRAWING PRIMITIVES =====

def _syringe(draw, cx, cy, scale=1.0):
    """Bold syringe."""
    s = scale
    bw, bh = int(16*s), int(72*s)
    x1, y1 = cx - bw, cy - bh//2
    x2, y2 = cx + bw, cy + bh//2
    draw.rectangle([x1, y1, x2, y2], outline=GOLD, width=LW)
    # plunger
    draw.line([cx - int(22*s), y1 - int(16*s), cx + int(22*s), y1 - int(16*s)], fill=GOLD, width=LW)
    draw.line([cx, y1 - int(16*s), cx, y1], fill=GOLD, width=LW)
    # needle
    draw.line([cx, y2, cx, y2 + int(28*s)], fill=GOLD, width=LW)
    draw.line([cx - int(6*s), y2 + int(28*s), cx + int(6*s), y2 + int(28*s)], fill=GOLD2, width=LW2)
    # graduation
    for i in range(1, 4):
        yy = y1 + i * (bh // 4)
        draw.line([x1, yy, x1 + int(10*s), yy], fill=GOLD2, width=LW2)
    # liquid
    liq = y1 + bh // 3
    draw.line([x1 + 3, liq, x2 - 3, liq], fill=GOLD, width=LW2)


def _droplet(draw, cx, cy, r=28):
    """Bold water droplet."""
    pts = [
        (cx, cy - int(r*2.0)),
        (cx - r, cy),
        (cx - int(r*0.9), cy + int(r*0.7)),
        (cx - int(r*0.5), cy + int(r*1.2)),
        (cx, cy + int(r*1.4)),
        (cx + int(r*0.5), cy + int(r*1.2)),
        (cx + int(r*0.9), cy + int(r*0.7)),
        (cx + r, cy),
    ]
    draw.polygon(pts, outline=GOLD, width=LW)


def _face_oval(draw, cx, cy, r=55):
    """Bold face outline."""
    draw.ellipse([cx - r, cy - int(r*1.3), cx + r, cy + int(r*1.3)], outline=GOLD, width=LW)
    # eyes
    ey = cy - int(r*0.3)
    for ex in [cx - int(r*0.35), cx + int(r*0.35)]:
        draw.ellipse([ex - 7, ey - 4, ex + 7, ey + 4], outline=GOLD, width=LW2)
    # nose
    draw.line([cx, cy - int(r*0.08), cx, cy + int(r*0.18)], fill=GOLD2, width=LW2)
    # lips
    ly = cy + int(r*0.4)
    draw.arc([cx - 15, ly - 5, cx + 15, ly + 10], 0, 180, fill=GOLD, width=LW2)


def _lips(draw, cx, cy, w=50, h=24):
    """Bold lips."""
    draw.arc([cx - w, cy - h - 5, cx, cy + 6], 200, 360, fill=GOLD, width=LW)
    draw.arc([cx, cy - h - 5, cx + w, cy + 6], 180, 340, fill=GOLD, width=LW)
    draw.arc([cx - w + 5, cy - 10, cx + w - 5, cy + h + 12], 0, 180, fill=GOLD, width=LW)
    draw.line([cx - w + 10, cy, cx + w - 10, cy], fill=GOLD2, width=LW2)


def _tooth(draw, cx, cy, r=40):
    """Bold tooth shape."""
    # Crown
    draw.arc([cx - r, cy - r - 10, cx + r, cy + r - 10], 180, 360, fill=GOLD, width=LW)
    # Sides
    draw.line([cx - r, cy - 10, cx - r + 5, cy + r - 5], fill=GOLD, width=LW)
    draw.line([cx + r, cy - 10, cx + r - 5, cy + r - 5], fill=GOLD, width=LW)
    # Roots (two)
    draw.line([cx - r + 5, cy + r - 5, cx - int(r*0.4), cy + r + 15], fill=GOLD, width=LW)
    draw.line([cx + r - 5, cy + r - 5, cx + int(r*0.4), cy + r + 15], fill=GOLD, width=LW)
    # Gap between roots
    draw.line([cx - int(r*0.4), cy + r + 15, cx, cy + r], fill=GOLD, width=LW)
    draw.line([cx + int(r*0.4), cy + r + 15, cx, cy + r], fill=GOLD, width=LW)


def _sparkle(draw, cx, cy, r=10, count=4):
    """Sparkle / star burst."""
    for i in range(count):
        angle = math.radians(i * (360 / count) + 45)
        x1 = cx + int((r * 0.3) * math.cos(angle))
        y1 = cy + int((r * 0.3) * math.sin(angle))
        x2 = cx + int(r * math.cos(angle))
        y2 = cy + int(r * math.sin(angle))
        draw.line([x1, y1, x2, y2], fill=GOLD, width=LW2)


def _sparkle_big(draw, cx, cy, r=18):
    """Big 8-point sparkle."""
    for i in range(8):
        angle = math.radians(i * 45)
        length = r if i % 2 == 0 else int(r * 0.6)
        x2 = cx + int(length * math.cos(angle))
        y2 = cy + int(length * math.sin(angle))
        draw.line([cx, cy, x2, y2], fill=GOLD, width=LW2)


def _arrow_up(draw, x, y, length=20):
    """Upward arrow."""
    draw.line([x, y + length, x, y], fill=GOLD, width=LW)
    draw.line([x - 6, y + 8, x, y], fill=GOLD, width=LW)
    draw.line([x + 6, y + 8, x, y], fill=GOLD, width=LW)


def _leaf_shape(draw, cx, cy, w=35, h=50):
    """Single leaf."""
    pts = [
        (cx, cy - h),
        (cx - w, cy - int(h*0.3)),
        (cx - int(w*0.9), cy + int(h*0.2)),
        (cx - int(w*0.5), cy + int(h*0.7)),
        (cx, cy + h),
        (cx + int(w*0.5), cy + int(h*0.7)),
        (cx + int(w*0.9), cy + int(h*0.2)),
        (cx + w, cy - int(h*0.3)),
    ]
    draw.polygon(pts, outline=GOLD, width=LW)
    draw.line([cx, cy - h + 5, cx, cy + h - 5], fill=GOLD, width=LW2)
    for dy, dx in [(-int(h*0.35), int(w*0.5)), (0, int(w*0.6)), (int(h*0.35), int(w*0.5))]:
        draw.line([cx, cy + dy, cx - dx, cy + dy - 8], fill=GOLD2, width=1)
        draw.line([cx, cy + dy, cx + dx, cy + dy - 8], fill=GOLD2, width=1)


def _flask(draw, cx, cy, with_needle=False):
    """Bold flask / beaker."""
    neck_w, neck_h = 14, 28
    fw = 34
    # Neck
    draw.rectangle([cx - neck_w, cy - 48, cx + neck_w, cy - 48 + neck_h], outline=GOLD, width=LW)
    # Cap
    draw.line([cx - neck_w - 6, cy - 50, cx + neck_w + 6, cy - 50], fill=GOLD, width=LW + 1)
    # Body
    draw.line([cx - neck_w, cy - 20, cx - fw, cy + 8], fill=GOLD, width=LW)
    draw.line([cx + neck_w, cy - 20, cx + fw, cy + 8], fill=GOLD, width=LW)
    draw.arc([cx - fw, cy + 8 - fw//2, cx + fw, cy + 8 + fw], 0, 180, fill=GOLD, width=LW)
    # Liquid
    draw.line([cx - fw + 6, cy + 8, cx + fw - 6, cy + 8], fill=GOLD, width=LW2)
    # Bubbles
    for bx, by in [(cx - 10, cy + 18), (cx + 7, cy + 12), (cx, cy + 26)]:
        draw.ellipse([bx - 4, by - 4, bx + 4, by + 4], outline=GOLD, width=LW2)
    if with_needle:
        nx = cx + 58
        ny = cy
        draw.line([nx, ny - 24, nx, ny + 24], fill=GOLD, width=LW)
        for i in range(-3, 4):
            draw.line([nx - 5, ny + i * 7, nx + 5, ny + i * 7], fill=GOLD, width=1)


def _tube(draw, cx, cy, with_needle=False):
    """Tube with drops (for PRX-T33)."""
    tw, th = 18, 55
    # Tube body
    draw.rounded_rectangle([cx - tw, cy - th, cx + tw, cy + th - 20], radius=8, outline=GOLD, width=LW)
    # Cap
    draw.rectangle([cx - tw - 3, cy - th - 12, cx + tw + 3, cy - th], outline=GOLD, width=LW)
    # Nozzle
    draw.line([cx - 6, cy + th - 20, cx - 6, cy + th - 10], fill=GOLD, width=LW2)
    draw.line([cx + 6, cy + th - 20, cx + 6, cy + th - 10], fill=GOLD, width=LW2)
    draw.line([cx - 6, cy + th - 10, cx + 6, cy + th - 10], fill=GOLD, width=LW2)
    # Drops
    for dx, dy in [(-8, th), (0, th + 12), (8, th)]:
        _droplet(draw, cx + dx, cy + dy, r=6)
    # Label line on tube
    draw.line([cx - tw + 5, cy - 10, cx + tw - 5, cy - 10], fill=GOLD2, width=1)
    draw.line([cx - tw + 5, cy, cx + tw - 5, cy], fill=GOLD2, width=1)
    if with_needle:
        nx = cx + 55
        ny = cy
        draw.line([nx, ny - 24, nx, ny + 24], fill=GOLD, width=LW)
        for i in range(-3, 4):
            draw.line([nx - 5, ny + i * 7, nx + 5, ny + i * 7], fill=GOLD, width=1)


def _dna_helix(draw, cx, cy, h=70, w=30):
    """DNA helix / molecule."""
    steps = 40
    for i in range(steps):
        t = i / (steps - 1)
        y = cy - h//2 + int(h * t)
        x1 = cx + int(w * math.sin(t * 4 * math.pi))
        x2 = cx - int(w * math.sin(t * 4 * math.pi))
        if i > 0:
            draw.line([px1, py, x1, y], fill=GOLD, width=LW)
            draw.line([px2, py, x2, y], fill=GOLD2, width=LW2)
        px1, px2, py = x1, x2, y
    # Cross rungs
    for i in range(0, steps, 5):
        t = i / (steps - 1)
        y = cy - h//2 + int(h * t)
        x1 = cx + int(w * math.sin(t * 4 * math.pi))
        x2 = cx - int(w * math.sin(t * 4 * math.pi))
        draw.line([x1, y, x2, y], fill=GOLD2, width=1)


def _eye_shape(draw, cx, cy, w=58, h=28):
    """Bold almond eye."""
    draw.arc([cx - w, cy - h*2, cx + w, cy + h], 200, 340, fill=GOLD, width=LW)
    draw.arc([cx - w, cy - h, cx + w, cy + h*2], 20, 160, fill=GOLD, width=LW)
    ir = 20
    draw.ellipse([cx - ir, cy - ir, cx + ir, cy + ir], outline=GOLD, width=LW)
    pr = 9
    draw.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=GOLD)
    draw.ellipse([cx - pr + 4, cy - pr + 2, cx - pr + 9, cy - pr + 7], fill=BG)
    # Lashes
    for i in range(-3, 4):
        angle = math.radians(i * 15 - 90)
        x1 = cx + int(w * 0.7 * math.cos(angle))
        y1 = cy + int(h * 0.5 * math.sin(angle)) - 6
        x2 = x1 + int(14 * math.cos(angle - 0.3))
        y2 = y1 + int(14 * math.sin(angle - 0.3))
        draw.line([x1, y1, x2, y2], fill=GOLD, width=LW2)


def _body_silhouette(draw, cx, cy, full=False):
    """Body outline — torso or full."""
    # Head
    draw.ellipse([cx - 15, cy - 75, cx + 15, cy - 45], outline=GOLD, width=LW)
    # Neck
    draw.line([cx - 6, cy - 45, cx - 6, cy - 35], fill=GOLD, width=LW2)
    draw.line([cx + 6, cy - 45, cx + 6, cy - 35], fill=GOLD, width=LW2)
    # Shoulders
    draw.line([cx - 6, cy - 35, cx - 40, cy - 20], fill=GOLD, width=LW)
    draw.line([cx + 6, cy - 35, cx + 40, cy - 20], fill=GOLD, width=LW)
    if full:
        # Torso
        draw.line([cx - 40, cy - 20, cx - 35, cy + 25], fill=GOLD, width=LW)
        draw.line([cx + 40, cy - 20, cx + 35, cy + 25], fill=GOLD, width=LW)
        # Hips
        draw.line([cx - 35, cy + 25, cx - 40, cy + 30], fill=GOLD, width=LW)
        draw.line([cx + 35, cy + 25, cx + 40, cy + 30], fill=GOLD, width=LW)
        # Legs
        draw.line([cx - 40, cy + 30, cx - 30, cy + 70], fill=GOLD, width=LW)
        draw.line([cx + 40, cy + 30, cx + 30, cy + 70], fill=GOLD, width=LW)
    else:
        # Just torso
        draw.line([cx - 40, cy - 20, cx - 30, cy + 40], fill=GOLD, width=LW)
        draw.line([cx + 40, cy - 20, cx + 30, cy + 40], fill=GOLD, width=LW)
        draw.arc([cx - 30, cy + 25, cx + 30, cy + 55], 0, 180, fill=GOLD, width=LW)


def _speech_bubble(draw, cx, cy, r=40):
    """Speech bubble."""
    draw.ellipse([cx - r, cy - int(r*0.7), cx + r, cy + int(r*0.7)], outline=GOLD, width=LW)
    # Tail
    pts = [
        (cx - int(r*0.2), cy + int(r*0.6)),
        (cx - int(r*0.5), cy + int(r*1.2)),
        (cx + int(r*0.15), cy + int(r*0.55)),
    ]
    draw.polygon(pts, fill=BG, outline=GOLD, width=LW2)
    # Inner fill to hide overlap
    draw.line([cx - int(r*0.18), cy + int(r*0.55), cx + int(r*0.13), cy + int(r*0.50)],
              fill=BG, width=LW + 2)
    # Dots inside
    for dx in [-15, 0, 15]:
        draw.ellipse([cx + dx - 4, cy - 4, cx + dx + 4, cy + 4], fill=GOLD)


def _person(draw, cx, cy, small=False):
    """Simple person icon."""
    s = 0.7 if small else 1.0
    r = int(14 * s)
    draw.ellipse([cx - r, cy - int(40*s) - r, cx + r, cy - int(40*s) + r], outline=GOLD, width=LW)
    # Body
    draw.line([cx, cy - int(40*s) + r, cx, cy + int(10*s)], fill=GOLD, width=LW)
    # Arms
    draw.line([cx - int(25*s), cy - int(15*s), cx + int(25*s), cy - int(15*s)], fill=GOLD, width=LW2)
    # Legs
    draw.line([cx, cy + int(10*s), cx - int(18*s), cy + int(40*s)], fill=GOLD, width=LW2)
    draw.line([cx, cy + int(10*s), cx + int(18*s), cy + int(40*s)], fill=GOLD, width=LW2)


def _screen(draw, cx, cy, w=45, h=35):
    """Monitor/screen."""
    draw.rectangle([cx - w, cy - h, cx + w, cy + h], outline=GOLD, width=LW)
    # Stand
    draw.line([cx, cy + h, cx, cy + h + 12], fill=GOLD, width=LW)
    draw.line([cx - 18, cy + h + 12, cx + 18, cy + h + 12], fill=GOLD, width=LW)
    # Screen glow
    draw.rectangle([cx - w + 6, cy - h + 6, cx + w - 6, cy + h - 6], outline=GOLD2, width=1)


def _hand_outline(draw, cx, cy):
    """Hand with droplets (hyperhidrosis)."""
    # Palm
    draw.rounded_rectangle([cx - 22, cy - 20, cx + 22, cy + 35], radius=10, outline=GOLD, width=LW)
    # Fingers (5)
    offsets = [(-18, -20), (-9, -35), (0, -42), (9, -35), (18, -20)]
    for i, (dx, dy) in enumerate(offsets):
        fw = 5 if i in (0, 4) else 6
        fh = 18 if i != 0 else 14
        draw.rounded_rectangle([cx + dx - fw, cy + dy - fh, cx + dx + fw, cy + dy],
                                radius=4, outline=GOLD, width=LW2)
    # Droplets
    for dx, dy in [(-15, 45), (0, 50), (15, 45), (-8, 58), (8, 58)]:
        _droplet(draw, cx + dx, cy + dy, r=5)


def _cheekbone(draw, cx, cy):
    """Face with cheekbone highlight."""
    _face_oval(draw, cx, cy, r=50)
    # Cheekbone highlight arcs
    draw.arc([cx - 50, cy - 10, cx - 10, cy + 25], 240, 350, fill=GOLD, width=LW + 1)
    draw.arc([cx + 10, cy - 10, cx + 50, cy + 25], 190, 300, fill=GOLD, width=LW + 1)


def _skin_layers(draw, cx, cy):
    """Skin cross-section layers."""
    w = 55
    for i, y_off in enumerate([-30, -5, 20, 45]):
        col = GOLD if i % 2 == 0 else GOLD2
        ww = LW if i == 0 else LW2
        # Wavy line
        pts = []
        for x in range(-w, w + 1, 4):
            y = cy + y_off + int(5 * math.sin(x * 0.1 + i))
            pts.append((cx + x, y))
        for j in range(len(pts) - 1):
            draw.line([pts[j], pts[j+1]], fill=col, width=ww)
    # Dots in layers
    for dx, dy in [(-20, 0), (10, 5), (-5, 25), (20, 30)]:
        draw.ellipse([cx + dx - 3, cy + dy - 3, cx + dx + 3, cy + dy + 3], fill=GOLD)


def _cell_pattern(draw, cx, cy, count=7, r=12):
    """Cell / circle pattern (exosomes)."""
    positions = [
        (cx, cy),
        (cx - 25, cy - 18), (cx + 25, cy - 18),
        (cx - 25, cy + 18), (cx + 25, cy + 18),
        (cx, cy - 35), (cx, cy + 35),
    ]
    for i, (px, py) in enumerate(positions[:count]):
        rr = r if i == 0 else int(r * 0.8)
        draw.ellipse([px - rr, py - rr, px + rr, py + rr], outline=GOLD, width=LW)
        # Inner circle
        ir = rr // 3
        draw.ellipse([px - ir, py - ir, px + ir, py + ir], fill=GOLD2)


def _molecule(draw, cx, cy):
    """Molecule structure."""
    nodes = [
        (cx, cy - 30), (cx - 30, cy), (cx + 30, cy),
        (cx - 15, cy + 30), (cx + 15, cy + 30),
    ]
    # Bonds
    bonds = [(0, 1), (0, 2), (1, 3), (2, 4), (3, 4)]
    for a, b in bonds:
        draw.line([nodes[a], nodes[b]], fill=GOLD2, width=LW2)
    # Atoms
    for nx, ny in nodes:
        draw.ellipse([nx - 8, ny - 8, nx + 8, ny + 8], fill=GOLD, outline=GOLD)


def _hair_strands(draw, cx, cy):
    """Hair / scalp with strands."""
    r = 48
    draw.arc([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=GOLD, width=LW)
    draw.line([cx - r, cy, cx - r, cy + 22], fill=GOLD, width=LW)
    draw.line([cx + r, cy, cx + r, cy + 22], fill=GOLD, width=LW)
    # Hair strands
    for angle_deg in range(-60, 70, 15):
        angle = math.radians(angle_deg - 90)
        x1 = cx + int(r * math.cos(angle))
        y1 = cy + int(r * math.sin(angle))
        x2 = cx + int((r + 30) * math.cos(angle))
        y2 = cy + int((r + 30) * math.sin(angle))
        draw.line([x1, y1, x2, y2], fill=GOLD, width=LW2)
    # Root dots
    for angle_deg in range(-50, 60, 20):
        angle = math.radians(angle_deg - 90)
        x = cx + int((r - 10) * math.cos(angle))
        y = cy + int((r - 10) * math.sin(angle))
        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=GOLD)


def _o2_molecule(draw, cx, cy):
    """O2 molecule with glow."""
    # Two O atoms
    r = 22
    draw.ellipse([cx - r - 15, cy - r, cx - 15 + r, cy + r], outline=GOLD, width=LW)
    draw.ellipse([cx + 15 - r, cy - r, cx + 15 + r, cy + r], outline=GOLD, width=LW)
    # O letters
    font = get_font(18)
    draw.text((cx - 22, cy - 10), "O", fill=GOLD, font=font)
    draw.text((cx + 8, cy - 10), "₂", fill=GOLD, font=get_font(14))
    # Glow rays around
    for angle_deg in range(0, 360, 30):
        angle = math.radians(angle_deg)
        x1 = cx + int(42 * math.cos(angle))
        y1 = cy + int(35 * math.sin(angle))
        x2 = cx + int(50 * math.cos(angle))
        y2 = cy + int(42 * math.sin(angle))
        draw.line([x1, y1, x2, y2], fill=GOLD2, width=1)


def _co2_bubbles(draw, cx, cy):
    """CO2 bubbles."""
    font = get_font(16)
    draw.text((cx - 18, cy - 50), "CO₂", fill=GOLD, font=font)
    # Rising bubbles
    bubbles = [
        (cx - 25, cy - 15, 12), (cx + 15, cy - 5, 10),
        (cx - 10, cy + 15, 14), (cx + 25, cy + 10, 9),
        (cx, cy + 35, 11), (cx - 20, cy + 40, 8),
        (cx + 10, cy + 45, 7), (cx + 30, cy + 30, 6),
    ]
    for bx, by, br in bubbles:
        draw.ellipse([bx - br, by - br, bx + br, by + br], outline=GOLD, width=LW2)
        # Highlight
        draw.arc([bx - br + 2, by - br + 2, bx, by], 200, 280, fill=GOLD, width=1)


def _botanical_leaves(draw, cx, cy):
    """Three-leaf botanical fan."""
    for angle_offset in [-35, 0, 35]:
        angle = math.radians(angle_offset)
        x1 = cx + int(5 * math.sin(angle))
        y1 = cy + 32
        x2 = cx + int(48 * math.sin(angle))
        y2 = cy - 42 + int(15 * abs(math.sin(angle)))
        draw.line([x1, y1, x2, y2], fill=GOLD, width=LW2)
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy) or 1
        nx = -dy / length * 17
        ny = dx / length * 17
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        pts = [
            (int(x1), int(y1)),
            (int(mid_x + nx), int(mid_y + ny)),
            (int(x2), int(y2)),
            (int(mid_x - nx), int(mid_y - ny)),
        ]
        draw.polygon(pts, outline=GOLD, width=LW)
    # Stem
    draw.line([cx, cy + 32, cx, cy + 55], fill=GOLD, width=LW)
    # Berries
    for dx, dy in [(-10, -48), (10, -45), (0, -55)]:
        draw.ellipse([cx + dx - 5, cy + dy - 5, cx + dx + 5, cy + dy + 5], outline=GOLD, width=LW2)


def _spa_flower(draw, cx, cy):
    """SPA flower with spiral."""
    r = 48
    draw.ellipse([cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8], outline=GOLD2, width=1)
    # Petals
    petal_r = 20
    for i in range(6):
        angle = math.radians(i * 60)
        px = cx + int(28 * math.cos(angle))
        py = cy + int(28 * math.sin(angle))
        draw.ellipse([px - petal_r, py - petal_r, px + petal_r, py + petal_r], outline=GOLD, width=LW)
    # Center
    draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], outline=GOLD, width=LW)
    # Spiral
    for i in range(25):
        t = i / 24 * 2.5 * math.pi
        rr = 2 + t * 2
        x = cx + int(rr * math.cos(t))
        y = cy + int(rr * math.sin(t))
        if i > 0:
            draw.line([px_s, py_s, x, y], fill=GOLD, width=LW2)
        px_s, py_s = x, y


def _face_sparkle_bubbles(draw, cx, cy):
    """Face with sparkle bubbles (WOW cleaning)."""
    _face_oval(draw, cx, cy, r=48)
    # Bubbles around face
    for dx, dy, r in [(-55, -20, 8), (-50, 15, 6), (55, -20, 8), (50, 15, 6),
                       (-45, 40, 5), (45, 40, 5), (-60, 0, 5), (60, 0, 5)]:
        draw.ellipse([cx + dx - r, cy + dy - r, cx + dx + r, cy + dy + r], outline=GOLD, width=LW2)
    _sparkle(draw, cx - 55, cy - 30, r=8)
    _sparkle(draw, cx + 55, cy - 30, r=8)


def _face_rays(draw, cx, cy):
    """Face with rays/glow (Siyannya)."""
    _face_oval(draw, cx, cy, r=45)
    # Rays emanating
    for angle_deg in range(0, 360, 25):
        angle = math.radians(angle_deg)
        inner = 55
        outer = 70
        x1 = cx + int(inner * math.cos(angle))
        y1 = cy + int(inner * math.sin(angle))
        x2 = cx + int(outer * math.cos(angle))
        y2 = cy + int(outer * math.sin(angle))
        draw.line([x1, y1, x2, y2], fill=GOLD, width=LW2)


def _soft_face_leaf(draw, cx, cy):
    """Soft face with leaf (teen cleaning)."""
    _face_oval(draw, cx - 15, cy, r=42)
    # Small leaf on right
    lx, ly = cx + 48, cy - 10
    pts = [
        (lx, ly - 25),
        (lx - 12, ly - 8),
        (lx - 10, ly + 10),
        (lx, ly + 25),
        (lx + 10, ly + 10),
        (lx + 12, ly - 8),
    ]
    draw.polygon(pts, outline=GOLD2, width=LW2)
    draw.line([lx, ly - 22, lx, ly + 22], fill=GOLD2, width=1)


def _hands_massage(draw, cx, cy):
    """Two hands in massage gesture."""
    # Left hand
    for dx_off in [-35, 35]:
        hx = cx + dx_off
        draw.rounded_rectangle([hx - 14, cy - 15, hx + 14, cy + 30], radius=8, outline=GOLD, width=LW)
        # Fingers
        for fi in range(-1, 2):
            fx = hx + fi * 8
            draw.rounded_rectangle([fx - 3, cy - 30, fx + 3, cy - 15], radius=2, outline=GOLD, width=LW2)
        # Thumb
        tx = hx + (12 if dx_off < 0 else -12)
        draw.rounded_rectangle([tx - 3, cy - 8, tx + 3, cy + 8], radius=2, outline=GOLD, width=LW2)
    # Wavy lines between (energy/massage)
    for y_off in [-5, 10, 25]:
        for x in range(-12, 13, 3):
            y = cy + y_off + int(4 * math.sin(x * 0.5))
            if x > -12:
                draw.line([cx + x - 3, cy + y_off + int(4 * math.sin((x-3)*0.5)),
                           cx + x, y], fill=GOLD2, width=1)


def _legs_waves(draw, cx, cy):
    """Legs with pressure waves (pressotherapy)."""
    # Two legs
    for dx in [-18, 18]:
        draw.rounded_rectangle([cx + dx - 10, cy - 60, cx + dx + 10, cy + 50],
                                radius=6, outline=GOLD, width=LW)
    # Pressure waves around
    for r_off in [30, 42, 54]:
        draw.arc([cx - r_off, cy - 40, cx + r_off, cy + 20], 240, 300, fill=GOLD2, width=LW2)
        draw.arc([cx - r_off, cy - 20, cx + r_off, cy + 40], 60, 120, fill=GOLD2, width=LW2)


def _body_part_hands(draw, cx, cy):
    """Body part with massage hands."""
    # Body segment (thigh/belly)
    draw.arc([cx - 45, cy - 30, cx + 45, cy + 50], 200, 340, fill=GOLD, width=LW)
    draw.arc([cx - 40, cy - 15, cx + 40, cy + 60], 20, 160, fill=GOLD, width=LW)
    # Two small hands
    for dx in [-50, 50]:
        hx = cx + dx
        draw.ellipse([hx - 8, cy + 5 - 8, hx + 8, cy + 5 + 8], outline=GOLD2, width=LW2)
        # Fingers as lines
        for fi in range(-1, 2):
            angle = math.radians(fi * 20 + (180 if dx > 0 else 0))
            draw.line([hx + int(8*math.cos(angle)), cy + 5 + int(8*math.sin(angle)),
                       hx + int(18*math.cos(angle)), cy + 5 + int(18*math.sin(angle))],
                      fill=GOLD2, width=LW2)


def _full_body_contour(draw, cx, cy):
    """Full body with contour lines."""
    _body_silhouette(draw, cx, cy, full=True)
    # Contour/shaping lines
    for dx_off in [-8, 8]:
        pts = []
        for i in range(10):
            y = cy - 30 + i * 10
            x = cx + dx_off + int(3 * math.sin(i * 0.8))
            pts.append((x, y))
        for j in range(len(pts) - 1):
            draw.line([pts[j], pts[j+1]], fill=GOLD2, width=1)


# ===== ICON GENERATORS =====

def icon_cat_injection(draw, cx, cy):
    """Category: syringe + droplet."""
    _syringe(draw, cx - 20, cy, scale=1.1)
    _droplet(draw, cx + 50, cy - 15, r=18)


def icon_cat_aparatna(draw, cx, cy):
    """Category: device/laser beam."""
    # Device box
    draw.rounded_rectangle([cx - 35, cy - 25, cx + 35, cy + 35], radius=8, outline=GOLD, width=LW)
    # Screen
    draw.rectangle([cx - 25, cy - 15, cx + 25, cy + 10], outline=GOLD2, width=LW2)
    # Laser beam going up-right
    bx, by = cx + 20, cy - 25
    draw.line([bx, by, bx + 30, by - 40], fill=GOLD, width=LW)
    draw.line([bx + 30, by - 40, bx + 35, by - 42], fill=GOLD, width=LW + 1)
    _sparkle(draw, bx + 38, by - 45, r=12)
    # Base
    draw.line([cx - 20, cy + 35, cx - 20, cy + 45], fill=GOLD, width=LW2)
    draw.line([cx + 20, cy + 35, cx + 20, cy + 45], fill=GOLD, width=LW2)
    draw.line([cx - 30, cy + 45, cx + 30, cy + 45], fill=GOLD, width=LW)


def icon_cat_body(draw, cx, cy):
    """Category: body silhouette."""
    _body_silhouette(draw, cx, cy, full=True)


def icon_cat_whitening(draw, cx, cy):
    """Category: tooth with sparkle."""
    _tooth(draw, cx, cy, r=42)
    _sparkle_big(draw, cx + 40, cy - 40, r=20)
    _sparkle(draw, cx - 38, cy - 35, r=10)


def icon_cat_care(draw, cx, cy):
    """Category: flower/leaf."""
    _spa_flower(draw, cx, cy)


def icon_botox_zones(draw, cx, cy, zones=1, dashed=False):
    """Syringe with zone dots. Dashed for Xeomin."""
    if dashed:
        # Draw syringe with dashed lines
        s = 1.0
        bw, bh = int(16*s), int(72*s)
        x1, y1 = cx - bw, cy - bh//2
        x2, y2 = cx + bw, cy + bh//2
        # Dashed rectangle
        for seg_start in range(y1, y2, 10):
            seg_end = min(seg_start + 6, y2)
            draw.line([x1, seg_start, x1, seg_end], fill=GOLD, width=LW)
            draw.line([x2, seg_start, x2, seg_end], fill=GOLD, width=LW)
        for seg_start in range(x1, x2, 10):
            seg_end = min(seg_start + 6, x2)
            draw.line([seg_start, y1, seg_end, y1], fill=GOLD, width=LW)
            draw.line([seg_start, y2, seg_end, y2], fill=GOLD, width=LW)
        # Plunger (dashed)
        draw.line([cx - 22, y1 - 16, cx + 22, y1 - 16], fill=GOLD, width=LW)
        draw.line([cx, y1 - 16, cx, y1], fill=GOLD, width=LW)
        # Needle
        draw.line([cx, y2, cx, y2 + 28], fill=GOLD, width=LW)
        # Graduation
        for i in range(1, 4):
            yy = y1 + i * (bh // 4)
            draw.line([x1, yy, x1 + 10, yy], fill=GOLD2, width=LW2)
    else:
        _syringe(draw, cx, cy, scale=1.0)

    # Zone dots
    if zones >= 1:
        for i in range(zones):
            dy = cy - 20 + i * 20
            draw.ellipse([cx - 45, dy - 5, cx - 35, dy + 5], fill=GOLD)


def icon_botox_fullface(draw, cx, cy, dashed=False):
    """Face + syringe (full face botox)."""
    _face_oval(draw, cx - 18, cy, r=42)
    sx = cx + 48
    if dashed:
        for seg in range(cy - 30, cy + 20, 10):
            draw.line([sx, seg, sx, min(seg + 6, cy + 20)], fill=GOLD, width=LW)
        draw.rectangle([sx - 7, cy - 18, sx + 7, cy + 18], outline=GOLD2, width=1)
    else:
        draw.line([sx, cy - 35, sx, cy + 25], fill=GOLD, width=LW)
        draw.rectangle([sx - 7, cy - 18, sx + 7, cy + 18], outline=GOLD, width=LW)
    draw.line([sx, cy + 18, sx, cy + 35], fill=GOLD, width=LW)
    draw.line([sx - 12, cy - 28, sx + 12, cy - 28], fill=GOLD, width=LW)


def icon_nefertiti(draw, cx, cy, dashed=False):
    """Profile with lift arrows."""
    points = [
        (cx - 10, cy - 58), (cx - 28, cy - 42), (cx - 32, cy - 20),
        (cx - 22, cy - 10), (cx - 30, cy + 5), (cx - 24, cy + 15),
        (cx - 32, cy + 32), (cx - 22, cy + 48), (cx + 5, cy + 52),
        (cx + 28, cy + 42), (cx + 22, cy + 58),
    ]
    w = LW
    for i in range(len(points) - 1):
        if dashed and i % 2 == 1:
            continue  # skip every other segment for dashed effect
        draw.line([points[i], points[i+1]], fill=GOLD, width=w)

    # Lift arrows
    for ax, ay in [(cx + 38, cy + 12), (cx + 52, cy - 5), (cx + 42, cy + 32)]:
        _arrow_up(draw, ax, ay, length=22)


def icon_hyperhidrosis(draw, cx, cy):
    """Hand with droplets."""
    _hand_outline(draw, cx, cy)


def icon_lips_variant(draw, cx, cy, variant="full"):
    """Lips variants."""
    if variant == "full":
        _lips(draw, cx, cy, w=52, h=26)
    elif variant == "side":
        # Side view — one larger arc
        draw.arc([cx - 40, cy - 20, cx + 30, cy + 30], 200, 360, fill=GOLD, width=LW)
        draw.arc([cx - 35, cy - 5, cx + 35, cy + 35], 0, 180, fill=GOLD, width=LW)
        draw.line([cx - 38, cy + 5, cx + 32, cy + 5], fill=GOLD2, width=LW2)
    elif variant == "outline":
        _lips(draw, cx, cy, w=50, h=24)
        # Just thinner, more delicate
    elif variant == "sparkle":
        _lips(draw, cx, cy, w=48, h=22)
        _sparkle_big(draw, cx + 40, cy - 20, r=14)


def icon_cheekbone(draw, cx, cy):
    """Cheekbone contouring."""
    _cheekbone(draw, cx, cy)


def icon_face_volume(draw, cx, cy, highlight=False, glow=False):
    """Face outline / volume."""
    _face_oval(draw, cx, cy, r=50)
    if highlight:
        # Cheek highlight
        draw.arc([cx - 30, cy - 5, cx - 5, cy + 20], 200, 350, fill=GOLD, width=LW)
        draw.arc([cx + 5, cy - 5, cx + 30, cy + 20], 190, 340, fill=GOLD, width=LW)
    if glow:
        # Glow around face
        for angle_deg in range(0, 360, 20):
            angle = math.radians(angle_deg)
            r1 = 60
            r2 = 68
            draw.line([cx + int(r1*math.cos(angle)), cy + int(r1*0.8*math.sin(angle)),
                       cx + int(r2*math.cos(angle)), cy + int(r2*0.8*math.sin(angle))],
                      fill=GOLD2, width=1)


def icon_dna(draw, cx, cy):
    """DNA helix for Rejuran HB."""
    _dna_helix(draw, cx, cy, h=80, w=32)


def icon_eye_treatment(draw, cx, cy):
    """Eye area treatment."""
    _eye_shape(draw, cx, cy)
    # Small droplet below
    _droplet(draw, cx + 45, cy + 15, r=8)


def icon_skin_layers(draw, cx, cy):
    """Skin layers for Rejuran S."""
    _skin_layers(draw, cx, cy)


def icon_exosomes(draw, cx, cy):
    """Cell / exosome pattern."""
    _cell_pattern(draw, cx, cy)


def icon_smart_biorevit(draw, cx, cy):
    """Droplet with sparkle."""
    _droplet(draw, cx, cy, r=30)
    _sparkle_big(draw, cx + 35, cy - 35, r=16)


def icon_vitaran_eye(draw, cx, cy):
    """Eye with droplet."""
    _eye_shape(draw, cx, cy - 10, w=55, h=25)
    _droplet(draw, cx + 40, cy + 25, r=10)


def icon_neauvia_hydro(draw, cx, cy):
    """Water drop."""
    _droplet(draw, cx, cy, r=35)
    # Inner shine
    draw.arc([cx - 12, cy - 8, cx + 5, cy + 10], 200, 340, fill=GOLD, width=LW2)


def icon_skin_booster(draw, cx, cy):
    """Skin glow."""
    _face_oval(draw, cx, cy, r=45)
    # Glow dots on cheeks
    for dx, dy in [(-20, 5), (-15, 15), (20, 5), (15, 15), (-25, -5), (25, -5)]:
        draw.ellipse([cx + dx - 3, cy + dy - 3, cx + dx + 3, cy + dy + 3], fill=GOLD)
    _sparkle(draw, cx, cy - 55, r=10)


def icon_hair(draw, cx, cy):
    """Hair strands for mesotherapy."""
    _hair_strands(draw, cx, cy)


def icon_skin_fill(draw, cx, cy):
    """Skin with fill (meso fill up)."""
    _skin_layers(draw, cx, cy - 10)
    # Syringe injecting
    sx = cx + 50
    draw.line([sx, cy - 40, sx - 20, cy - 5], fill=GOLD, width=LW)
    draw.line([sx - 20, cy - 5, sx - 22, cy + 5], fill=GOLD, width=LW)
    _sparkle(draw, sx - 22, cy + 8, r=8)


def icon_molecule(draw, cx, cy):
    """Molecule for Plinest One."""
    _molecule(draw, cx, cy)


def icon_mesobotox(draw, cx, cy):
    """Face with smooth lines (Monaco mesobotox)."""
    _face_oval(draw, cx, cy, r=48)
    # Smooth horizontal lines across forehead and cheeks
    for y_off in [-30, -18, 15, 25]:
        w = 25 if abs(y_off) > 20 else 30
        draw.line([cx - w, cy + y_off, cx + w, cy + y_off], fill=GOLD2, width=1)
    _sparkle(draw, cx + 45, cy - 40, r=8)


def icon_face_slim(draw, cx, cy):
    """Face slim (lipolytics face)."""
    _face_oval(draw, cx, cy, r=48)
    # Slim arrows pointing inward on jaw
    for dx in [-1, 1]:
        ax = cx + dx * 40
        draw.line([ax + dx * 15, cy + 30, ax, cy + 30], fill=GOLD, width=LW)
        draw.line([ax + dx * 5, cy + 25, ax, cy + 30], fill=GOLD, width=LW)
        draw.line([ax + dx * 5, cy + 35, ax, cy + 30], fill=GOLD, width=LW)


def icon_body_slim(draw, cx, cy):
    """Body slim (lipolytics body)."""
    _body_silhouette(draw, cx, cy, full=True)
    # Slim arrows
    for dy_off in [-10, 15]:
        for dx in [-1, 1]:
            ax = cx + dx * 48
            draw.line([ax + dx * 15, cy + dy_off, ax, cy + dy_off], fill=GOLD, width=LW2)
            draw.line([ax + dx * 5, cy + dy_off - 5, ax, cy + dy_off], fill=GOLD, width=LW2)
            draw.line([ax + dx * 5, cy + dy_off + 5, ax, cy + dy_off], fill=GOLD, width=LW2)


def icon_dissolve(draw, cx, cy):
    """Dissolve symbol (hyaluronidase)."""
    # Broken circle with particles dispersing
    draw.arc([cx - 35, cy - 35, cx + 35, cy + 35], 30, 150, fill=GOLD, width=LW)
    draw.arc([cx - 35, cy - 35, cx + 35, cy + 35], 200, 320, fill=GOLD, width=LW)
    # Dispersing particles
    for angle_deg in [160, 170, 180, 330, 340, 350]:
        angle = math.radians(angle_deg)
        for r_off in [42, 52, 62]:
            x = cx + int(r_off * math.cos(angle))
            y = cy + int(r_off * math.sin(angle))
            sz = max(2, 5 - (r_off - 42) // 10)
            draw.ellipse([x - sz, y - sz, x + sz, y + sz], fill=GOLD2)


def icon_touchup_pen(draw, cx, cy):
    """Touch-up pen (filler correction)."""
    # Pen body at angle
    angle = math.radians(-45)
    length = 80
    px1 = cx + int(length/2 * math.cos(angle))
    py1 = cy + int(length/2 * math.sin(angle))
    px2 = cx - int(length/2 * math.cos(angle))
    py2 = cy - int(length/2 * math.sin(angle))
    # Pen body
    perp = math.radians(-45 + 90)
    w = 8
    corners = [
        (px1 + int(w*math.cos(perp)), py1 + int(w*math.sin(perp))),
        (px1 - int(w*math.cos(perp)), py1 - int(w*math.sin(perp))),
        (px2 - int(w*math.cos(perp)), py2 - int(w*math.sin(perp))),
        (px2 + int(w*math.cos(perp)), py2 + int(w*math.sin(perp))),
    ]
    draw.polygon(corners, outline=GOLD, width=LW)
    # Tip
    tip_x = px2 - int(15 * math.cos(angle))
    tip_y = py2 - int(15 * math.sin(angle))
    draw.line([px2, py2, tip_x, tip_y], fill=GOLD, width=LW)
    # Small dots at tip (correction)
    _sparkle(draw, tip_x - 5, tip_y - 5, r=8)


def icon_adjustment_arrows(draw, cx, cy):
    """Adjustment arrows (botulotoxin correction)."""
    # Circular arrows
    draw.arc([cx - 35, cy - 35, cx + 35, cy + 35], 30, 150, fill=GOLD, width=LW)
    draw.arc([cx - 35, cy - 35, cx + 35, cy + 35], 210, 330, fill=GOLD, width=LW)
    # Arrow heads
    for angle_deg, da in [(150, 1), (330, 1)]:
        angle = math.radians(angle_deg)
        ax = cx + int(35 * math.cos(angle))
        ay = cy + int(35 * math.sin(angle))
        for offset in [-25, 25]:
            a2 = math.radians(angle_deg + offset)
            draw.line([ax, ay,
                       ax - int(12 * math.cos(a2)),
                       ay - int(12 * math.sin(a2))], fill=GOLD, width=LW)
    # Center syringe small
    draw.line([cx, cy - 15, cx, cy + 15], fill=GOLD2, width=LW2)
    draw.line([cx - 6, cy - 10, cx + 6, cy - 10], fill=GOLD2, width=LW2)
    draw.ellipse([cx - 3, cy + 12, cx + 3, cy + 18], fill=GOLD2)


def icon_tooth_sparkle(draw, cx, cy, intensity=1):
    """Tooth with sparkle (whitening). intensity 1=small, 2=medium, 3=big."""
    _tooth(draw, cx - 5, cy + 5, r=38)
    if intensity == 1:
        _sparkle(draw, cx + 35, cy - 35, r=12)
    elif intensity == 2:
        _sparkle_big(draw, cx + 35, cy - 35, r=16)
        _sparkle(draw, cx - 40, cy - 30, r=8)
    else:
        _sparkle_big(draw, cx + 38, cy - 38, r=22)
        _sparkle(draw, cx - 42, cy - 32, r=12)
        _sparkle(draw, cx + 45, cy + 5, r=8)
        # Extra rays
        for angle_deg in range(0, 360, 45):
            angle = math.radians(angle_deg)
            x1 = cx - 5 + int(48 * math.cos(angle))
            y1 = cy + 5 + int(52 * math.sin(angle))
            x2 = cx - 5 + int(58 * math.cos(angle))
            y2 = cy + 5 + int(62 * math.sin(angle))
            draw.line([x1, y1, x2, y2], fill=GOLD2, width=1)


def icon_consultation(draw, cx, cy):
    """Speech bubble."""
    _speech_bubble(draw, cx, cy)


def icon_offline_consultation(draw, cx, cy):
    """Person + speech bubble."""
    _person(draw, cx - 30, cy + 10, small=True)
    _speech_bubble(draw, cx + 25, cy - 15, r=30)


def icon_online_consultation(draw, cx, cy):
    """Screen + speech bubble."""
    _screen(draw, cx - 15, cy + 5, w=40, h=30)
    _speech_bubble(draw, cx + 45, cy - 25, r=22)


# ===== ALL PROCEDURES =====

ICONS = [
    # --- CATEGORIES (no label) ---
    ("cat_injection", None, icon_cat_injection),
    ("cat_aparatna", None, icon_cat_aparatna),
    ("cat_body", None, icon_cat_body),
    ("cat_whitening", None, icon_cat_whitening),
    ("cat_care", None, icon_cat_care),

    # --- Ін'єкційна: Ботулінотерапія Neuronox ---
    ("botox_1z_neuronox", "Ботулінотерапія 1 зона\n(Neuronox)",
     lambda d, cx, cy: icon_botox_zones(d, cx, cy, zones=1, dashed=False)),
    ("botox_2z_neuronox", "Ботулінотерапія 2 зони\n(Neuronox)",
     lambda d, cx, cy: icon_botox_zones(d, cx, cy, zones=2, dashed=False)),
    ("botox_3z_neuronox", "Ботулінотерапія 3 зони\n(Neuronox)",
     lambda d, cx, cy: icon_botox_zones(d, cx, cy, zones=3, dashed=False)),
    ("botox_ff_neuronox", "Ботулінотерапія Full Face\n(Neuronox)",
     lambda d, cx, cy: icon_botox_fullface(d, cx, cy, dashed=False)),
    ("nefertiti_neuronox", "Ліфтинг Ніфертіті\n(Neuronox)",
     lambda d, cx, cy: icon_nefertiti(d, cx, cy, dashed=False)),

    # --- Ботулінотерапія Xeomin (dashed style) ---
    ("botox_1z_xeomin", "Ботулінотерапія 1 зона\n(Xeomin)",
     lambda d, cx, cy: icon_botox_zones(d, cx, cy, zones=1, dashed=True)),
    ("botox_2z_xeomin", "Ботулінотерапія 2 зони\n(Xeomin)",
     lambda d, cx, cy: icon_botox_zones(d, cx, cy, zones=2, dashed=True)),
    ("botox_3z_xeomin", "Ботулінотерапія 3 зони\n(Xeomin)",
     lambda d, cx, cy: icon_botox_zones(d, cx, cy, zones=3, dashed=True)),
    ("botox_ff_xeomin", "Ботулінотерапія Full Face\n(Xeomin)",
     lambda d, cx, cy: icon_botox_fullface(d, cx, cy, dashed=True)),
    ("nefertiti_xeomin", "Ліфтинг Ніфертіті\n(Xeomin)",
     lambda d, cx, cy: icon_nefertiti(d, cx, cy, dashed=True)),

    # --- Гіпергідроз ---
    ("hyperhidrosis", "Лікування гіпергідрозу\n(Botox)", icon_hyperhidrosis),

    # --- Контурна пластика ---
    ("kontur_neuramis", "Контурна пластика\nNeuramis Deep",
     lambda d, cx, cy: icon_lips_variant(d, cx, cy, variant="full")),
    ("kontur_saypha", "Контурна пластика\nSaypha Filler",
     lambda d, cx, cy: icon_lips_variant(d, cx, cy, variant="side")),
    ("kontur_perfecta", "Контурна пластика\nPerfecta",
     lambda d, cx, cy: icon_lips_variant(d, cx, cy, variant="outline")),
    ("kontur_genyal", "Контурна пластика\nGenyal / Xcelence 3", icon_cheekbone),
    ("kontur_neauvia_lips", "Контурна пластика\nNeauvia Intense Lips",
     lambda d, cx, cy: icon_lips_variant(d, cx, cy, variant="sparkle")),
    ("kontur_neuramis_vol", "Контурна пластика\nNeuramis Volume",
     lambda d, cx, cy: icon_face_volume(d, cx, cy)),
    ("kontur_saypha_vol", "Контурна пластика\nSaypha Volume",
     lambda d, cx, cy: icon_face_volume(d, cx, cy, highlight=True)),
    ("kontur_neauvia_stim", "Контурна пластика\nNeauvia Stimulate",
     lambda d, cx, cy: icon_face_volume(d, cx, cy, glow=True)),

    # --- Біорепарація ---
    ("biorep_rejuran_hb", "Біорепарація\nRejuran HB", icon_dna),
    ("biorep_rejuran_i", "Біорепарація\nRejuran I", icon_eye_treatment),
    ("biorep_rejuran_s", "Біорепарація\nRejuran S", icon_skin_layers),
    ("biorep_exosomes", "Біорепарація Екзосоми\n(Exoxe) 2.5 ml", icon_exosomes),

    # --- Біоревіталізація ---
    ("biorevit_smart", "Smart-\nбіоревіталізація", icon_smart_biorevit),
    ("biorevit_vitaran_eye", "Біоревіталізація\nVitaran Tox & Eye", icon_vitaran_eye),
    ("biorevit_neauvia_hydro", "Біоревіталізація\nNeauvia Hydro Deluxe", icon_neauvia_hydro),
    ("biorevit_skinbooster", "Біоревіталізація\nSkin Booster", icon_skin_booster),

    # --- Мезотерапія ---
    ("mezo_hair", "Мезотерапія\nHair Loss / Hair Vital", icon_hair),
    ("mezo_fillup", "Мезотерапія\nFill Up", icon_skin_fill),
    ("mezo_plinest", "Мезотерапія\nPlinest One (4 ml)", icon_molecule),
    ("mesobotox_monaco", "Мезоботокс\n«Монако» (4 ml)", icon_mesobotox),

    # --- Ліполітики ---
    ("lipo_face", "Ліполітики\n(обличчя, 4 мл)", icon_face_slim),
    ("lipo_body", "Ліполітики\n(тіло, 10 мл)", icon_body_slim),

    # --- Корекції ---
    ("hyaluronidase", "Гіалуронідаза\n(розчинення філера)", icon_dissolve),
    ("correction_filler", "Корекція філера", icon_touchup_pen),
    ("correction_botox", "Корекція\nботулотоксину", icon_adjustment_arrows),

    # --- Апаратна косметологія ---
    ("wow_cleaning", "WOW-чистка\nобличчя",
     lambda d, cx, cy: _face_sparkle_bubbles(d, cx, cy)),
    ("wow_glow", "WOW-чистка\n«Сяяння»",
     lambda d, cx, cy: _face_rays(d, cx, cy)),
    ("teen_cleaning", "Підліткова\nделікатна чистка",
     lambda d, cx, cy: _soft_face_leaf(d, cx, cy)),
    ("oxygen_glow", "Кисневий догляд\nGlow Skin",
     lambda d, cx, cy: _o2_molecule(d, cx, cy)),
    ("carboxy", "Карбокситерапія",
     lambda d, cx, cy: _co2_bubbles(d, cx, cy)),

    # --- Доглядові процедури ---
    ("kemikum", "KEMIKUM",
     lambda d, cx, cy: _flask(d, cx, cy, with_needle=False)),
    ("kemikum_microneedling", "KEMIKUM +\nмікронідлінг",
     lambda d, cx, cy: _flask(d, cx - 18, cy, with_needle=True)),
    ("prx_t33", "PRX-T33",
     lambda d, cx, cy: _tube(d, cx, cy, with_needle=False)),
    ("prx_t33_microneedling", "PRX-T33 +\nмікронідлінг",
     lambda d, cx, cy: _tube(d, cx - 18, cy, with_needle=True)),
    ("acid_peeling", "Азелаїновий / Мигдальний /\nФеруловий",
     lambda d, cx, cy: _botanical_leaves(d, cx, cy)),
    ("spa_christina", "SPA-догляд\nвід Christina",
     lambda d, cx, cy: _spa_flower(d, cx, cy)),

    # --- Догляд за тілом ---
    ("body_part_massage", "Моделювання\nокремої ділянки",
     lambda d, cx, cy: _body_part_hands(d, cx, cy)),
    ("body_full_contour", "Моделювання\nвсього тіла",
     lambda d, cx, cy: _full_body_contour(d, cx, cy)),
    ("body_relax_massage", "Загальний релакс-масаж\nвсього тіла",
     lambda d, cx, cy: _hands_massage(d, cx, cy)),
    ("pressotherapy", "Пресотерапія\n«Легкість тіла»",
     lambda d, cx, cy: _legs_waves(d, cx, cy)),

    # --- Відбілювання зубів ---
    ("whitening_light", "Відбілювання зубів\nLight",
     lambda d, cx, cy: icon_tooth_sparkle(d, cx, cy, intensity=1)),
    ("whitening_medium", "Відбілювання зубів\nMedium",
     lambda d, cx, cy: icon_tooth_sparkle(d, cx, cy, intensity=2)),
    ("whitening_maximum", "Відбілювання зубів\nMaximum",
     lambda d, cx, cy: icon_tooth_sparkle(d, cx, cy, intensity=3)),

    # --- Top-level ---
    ("consultation", "Консультація", icon_consultation),
    ("consultation_offline", "Офлайн-\nконсультація", icon_offline_consultation),
    ("consultation_online", "Онлайн-\nконсультація", icon_online_consultation),
]


def generate_all():
    print(f"Generating {len(ICONS)} icons to {OUT_DIR}/\n")

    for filename, label, draw_fn in ICONS:
        img, draw = new_icon()

        # For categories, use full center (no label offset)
        if label is None:
            draw_fn(draw, CX, CY + 18)
        else:
            draw_fn(draw, CX, CY)

        if label is not None:
            # Handle multi-line labels passed with \n
            clean_label = label.replace("\n", " ")
            draw_label(draw, clean_label)

        save_icon(img, f"{filename}.png")

    print(f"\nDone! {len(ICONS)} icons saved to {OUT_DIR}/")


if __name__ == "__main__":
    generate_all()
