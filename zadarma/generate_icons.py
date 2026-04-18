#!/usr/bin/env python3
"""
Generate stylized gold-on-black PNG icons (260x260) for WLaunch CRM services.
Minimalistic thin line art style — luxury cosmetic brand aesthetic.
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont

# --- Config ---
SIZE = 260
BG = "#111111"
GOLD = "#C9A96E"
GOLD2 = "#D4AF37"  # brighter accent
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wl_icons")
os.makedirs(OUT_DIR, exist_ok=True)

# Font — macOS Helvetica, fallback to default
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

CX, CY = SIZE // 2, SIZE // 2 - 20  # center shifted up for label space


# --- Drawing helpers ---

def new_icon():
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)
    return img, draw


def draw_label(draw, text, y_start=210):
    """Draw 1-2 line gold label centered at bottom."""
    # Split into max 2 lines if too long
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=FONT_LABEL)
        if bbox[2] - bbox[0] > SIZE - 20:
            if current:
                lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)

    # Max 2 lines
    if len(lines) > 2:
        lines = [" ".join(lines[:len(lines)//2]), " ".join(lines[len(lines)//2:])]

    for i, line in enumerate(lines):
        font = FONT_LABEL if len(lines) == 1 else FONT_SMALL
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (SIZE - tw) // 2
        y = y_start + i * 18
        draw.text((x, y), line, fill=GOLD, font=font)


def save_icon(img, filename):
    path = os.path.join(OUT_DIR, filename)
    img.save(path, "PNG")
    print(f"  -> {path}")


# --- Icon drawing functions ---

def draw_syringe(draw, cx, cy, scale=1.0):
    """Minimalistic syringe icon."""
    s = scale
    # Barrel
    bw, bh = int(14*s), int(70*s)
    x1 = cx - bw
    y1 = cy - bh//2
    x2 = cx + bw
    y2 = cy + bh//2
    draw.rectangle([x1, y1, x2, y2], outline=GOLD, width=2)

    # Plunger handle (top)
    draw.line([cx - int(20*s), y1 - int(15*s), cx + int(20*s), y1 - int(15*s)], fill=GOLD, width=2)
    draw.line([cx, y1 - int(15*s), cx, y1], fill=GOLD, width=2)

    # Needle (bottom)
    draw.line([cx, y2, cx, y2 + int(25*s)], fill=GOLD, width=2)
    draw.line([cx - int(5*s), y2 + int(25*s), cx + int(5*s), y2 + int(25*s)], fill=GOLD, width=1)

    # Graduation marks
    for i in range(1, 4):
        yy = y1 + i * (bh // 4)
        draw.line([x1, yy, x1 + int(8*s), yy], fill=GOLD, width=1)

    # Liquid level
    draw.line([x1 + 2, y1 + bh//3, x2 - 2, y1 + bh//3], fill=GOLD2, width=1)


def draw_face_outline(draw, cx, cy, r=50):
    """Minimalistic face oval."""
    draw.ellipse([cx - r, cy - int(r*1.3), cx + r, cy + int(r*1.3)], outline=GOLD, width=2)
    # Eyes
    ey = cy - int(r*0.3)
    for ex in [cx - int(r*0.35), cx + int(r*0.35)]:
        draw.ellipse([ex - 5, ey - 3, ex + 5, ey + 3], outline=GOLD, width=1)
    # Nose
    draw.line([cx, cy - int(r*0.1), cx, cy + int(r*0.15)], fill=GOLD, width=1)
    # Lips
    ly = cy + int(r*0.4)
    draw.arc([cx - 12, ly - 4, cx + 12, ly + 8], 0, 180, fill=GOLD, width=1)


def draw_face_with_syringe(draw, cx, cy):
    """Face outline + small syringe."""
    draw_face_outline(draw, cx - 15, cy, r=45)
    # Small syringe on the right side
    sx = cx + 45
    sy = cy - 10
    # Diagonal syringe
    draw.line([sx, sy - 30, sx, sy + 20], fill=GOLD, width=2)
    draw.rectangle([sx - 6, sy - 15, sx + 6, sy + 15], outline=GOLD, width=2)
    draw.line([sx, sy + 15, sx, sy + 30], fill=GOLD, width=2)
    draw.line([sx - 10, sy - 25, sx + 10, sy - 25], fill=GOLD, width=2)
    draw.line([sx, sy - 30, sx, sy - 25], fill=GOLD, width=2)


def draw_face_profile_lift(draw, cx, cy):
    """Face profile with upward lift arrows (Nefertiti)."""
    # Profile curve (left side of face)
    points = [
        (cx - 10, cy - 55),  # forehead
        (cx - 25, cy - 40),
        (cx - 30, cy - 20),  # nose
        (cx - 20, cy - 10),
        (cx - 28, cy + 5),   # lips
        (cx - 22, cy + 15),
        (cx - 30, cy + 30),  # chin
        (cx - 20, cy + 45),  # jawline
        (cx + 5, cy + 50),
        (cx + 25, cy + 40),  # neck
        (cx + 20, cy + 55),
    ]
    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill=GOLD, width=2)

    # Lift arrows on the right side (upward)
    for i, (ax, ay) in enumerate([(cx + 35, cy + 10), (cx + 50, cy - 5), (cx + 40, cy + 30)]):
        draw.line([ax, ay + 20, ax, ay], fill=GOLD2, width=2)
        # Arrow head
        draw.line([ax - 5, ay + 7, ax, ay], fill=GOLD2, width=2)
        draw.line([ax + 5, ay + 7, ax, ay], fill=GOLD2, width=2)


def draw_lips(draw, cx, cy, variant=0):
    """Minimalistic lips icon for contouring."""
    # Upper lip (cupid's bow)
    w = 45
    h = 20

    # Upper lip curves
    draw.arc([cx - w, cy - h - 5, cx, cy + 5], 200, 360, fill=GOLD, width=2)
    draw.arc([cx, cy - h - 5, cx + w, cy + 5], 180, 340, fill=GOLD, width=2)

    # Lower lip
    draw.arc([cx - w + 5, cy - 8, cx + w - 5, cy + h + 10], 0, 180, fill=GOLD, width=2)

    # Center line
    draw.line([cx - w + 8, cy, cx + w - 8, cy], fill=GOLD, width=1)

    # Small accent based on variant
    if variant == 1:
        draw.ellipse([cx - 3, cy + 5, cx + 3, cy + 11], outline=GOLD2, width=1)
    elif variant == 2:
        # Subtle shine mark
        draw.arc([cx - 10, cy + 2, cx + 10, cy + 12], 20, 160, fill=GOLD2, width=1)


def draw_hair_scalp(draw, cx, cy):
    """Hair/scalp icon for mesotherapy."""
    # Head outline (top half)
    r = 45
    draw.arc([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=GOLD, width=2)
    draw.line([cx - r, cy, cx - r, cy + 20], fill=GOLD, width=2)
    draw.line([cx + r, cy, cx + r, cy + 20], fill=GOLD, width=2)

    # Hair strands on top
    for angle_deg in range(-60, 70, 20):
        angle = math.radians(angle_deg - 90)
        x1 = cx + int(r * math.cos(angle))
        y1 = cy + int(r * math.sin(angle))
        x2 = cx + int((r + 25) * math.cos(angle))
        y2 = cy + int((r + 25) * math.sin(angle))
        draw.line([x1, y1, x2, y2], fill=GOLD, width=1)

    # Root dots
    for angle_deg in range(-50, 60, 25):
        angle = math.radians(angle_deg - 90)
        x = cx + int((r - 8) * math.cos(angle))
        y = cy + int((r - 8) * math.sin(angle))
        draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=GOLD2)


def draw_droplet_skin(draw, cx, cy):
    """Droplet / skin booster icon."""
    # Droplet shape
    points = []
    for i in range(50):
        t = i / 49
        if t < 0.5:
            # Top part — converge to point
            tt = t * 2
            x = cx + int(30 * math.sin(math.pi * tt) * tt)
            y = cy - 50 + int(50 * tt)
            points.append((cx - int(30 * math.sin(math.pi * tt) * (1-tt*0.3)), y))
        else:
            # Bottom circle
            angle = math.pi * (t - 0.5) * 2
            x = cx + int(30 * math.sin(angle))
            y = cy + int(30 * math.cos(angle))

    # Simplified droplet
    # Top point
    draw.polygon([
        (cx, cy - 55),
        (cx - 30, cy + 5),
        (cx - 28, cy + 20),
        (cx - 15, cy + 35),
        (cx, cy + 40),
        (cx + 15, cy + 35),
        (cx + 28, cy + 20),
        (cx + 30, cy + 5),
    ], outline=GOLD, width=2)

    # Inner glow circles
    draw.ellipse([cx - 8, cy - 5, cx + 8, cy + 11], outline=GOLD2, width=1)
    draw.ellipse([cx - 3, cy, cx + 3, cy + 6], fill=GOLD2)

    # Skin texture dots around
    for dx, dy in [(-45, 10), (-40, -15), (45, 10), (40, -15), (-35, 30), (35, 30)]:
        draw.ellipse([cx+dx-2, cy+dy-2, cx+dx+2, cy+dy+2], outline=GOLD, width=1)


def draw_eye(draw, cx, cy):
    """Eye icon for eye treatments."""
    # Eye shape — almond
    w, h = 55, 25

    # Upper lid
    draw.arc([cx - w, cy - h*2, cx + w, cy + h], 200, 340, fill=GOLD, width=2)
    # Lower lid
    draw.arc([cx - w, cy - h, cx + w, cy + h*2], 20, 160, fill=GOLD, width=2)

    # Iris
    ir = 18
    draw.ellipse([cx - ir, cy - ir, cx + ir, cy + ir], outline=GOLD, width=2)

    # Pupil
    pr = 8
    draw.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=GOLD2)

    # Highlight
    draw.ellipse([cx - pr + 4, cy - pr + 2, cx - pr + 8, cy - pr + 6], fill=BG)

    # Lashes (upper)
    for i in range(-3, 4):
        angle = math.radians(i * 15 - 90)
        x1 = cx + int(w * 0.7 * math.cos(angle))
        y1 = cy + int(h * 0.5 * math.sin(angle)) - 5
        x2 = x1 + int(12 * math.cos(angle - 0.3))
        y2 = y1 + int(12 * math.sin(angle - 0.3))
        draw.line([x1, y1, x2, y2], fill=GOLD, width=1)


def draw_leaf(draw, cx, cy, with_needle=False):
    """Leaf / nature icon for peeling."""
    # Leaf shape
    pts = [
        (cx, cy - 50),
        (cx - 30, cy - 25),
        (cx - 35, cy),
        (cx - 25, cy + 25),
        (cx, cy + 45),
        (cx + 25, cy + 25),
        (cx + 35, cy),
        (cx + 30, cy - 25),
    ]
    draw.polygon(pts, outline=GOLD, width=2)

    # Vein lines
    draw.line([cx, cy - 45, cx, cy + 40], fill=GOLD, width=1)
    for dy, dx in [(-20, 18), (0, 22), (20, 18)]:
        draw.line([cx, cy + dy, cx - dx, cy + dy - 8], fill=GOLD, width=1)
        draw.line([cx, cy + dy, cx + dx, cy + dy - 8], fill=GOLD, width=1)

    if with_needle:
        # Small needle/roller on the right
        nx = cx + 50
        ny = cy - 10
        draw.line([nx, ny - 25, nx, ny + 25], fill=GOLD2, width=2)
        # Needle tip dots
        for i in range(-2, 3):
            draw.line([nx - 3, ny + i*8, nx + 3, ny + i*8], fill=GOLD2, width=1)


def draw_flask(draw, cx, cy, with_needle=False):
    """Flask / test tube icon."""
    # Flask body
    fw, neck_w = 30, 12
    neck_h = 25
    body_h = 50

    # Neck
    draw.rectangle([cx - neck_w, cy - 45, cx + neck_w, cy - 45 + neck_h], outline=GOLD, width=2)
    # Cap
    draw.line([cx - neck_w - 5, cy - 47, cx + neck_w + 5, cy - 47], fill=GOLD, width=3)

    # Body (wider bottom)
    draw.line([cx - neck_w, cy - 20, cx - fw, cy + 5], fill=GOLD, width=2)
    draw.line([cx + neck_w, cy - 20, cx + fw, cy + 5], fill=GOLD, width=2)
    draw.arc([cx - fw, cy + 5 - fw//2, cx + fw, cy + 5 + fw], 0, 180, fill=GOLD, width=2)

    # Liquid level
    liq_y = cy + 5
    draw.line([cx - fw + 5, liq_y, cx + fw - 5, liq_y], fill=GOLD2, width=1)

    # Bubbles
    for bx, by in [(cx - 8, cy + 15), (cx + 5, cy + 10), (cx, cy + 22)]:
        draw.ellipse([bx - 3, by - 3, bx + 3, by + 3], outline=GOLD2, width=1)

    if with_needle:
        # Micro-needle roller on right
        nx = cx + 55
        ny = cy
        draw.line([nx, ny - 20, nx, ny + 20], fill=GOLD2, width=2)
        for i in range(-2, 3):
            draw.line([nx - 4, ny + i*7, nx + 4, ny + i*7], fill=GOLD2, width=1)


def draw_botanical(draw, cx, cy):
    """Botanical / multi-leaf icon for acid peels."""
    # Three leaves in a fan arrangement
    for angle_offset in [-35, 0, 35]:
        angle = math.radians(angle_offset)
        # Leaf center line
        x1 = cx + int(5 * math.sin(angle))
        y1 = cy + 30
        x2 = cx + int(45 * math.sin(angle))
        y2 = cy - 40 + int(15 * abs(math.sin(angle)))
        draw.line([x1, y1, x2, y2], fill=GOLD, width=1)

        # Leaf outline (ellipse rotated) — approximate with polygon
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy)
        if length == 0:
            continue
        nx = -dy / length * 15
        ny = dx / length * 15

        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2

        pts = [
            (int(x1), int(y1)),
            (int(mid_x + nx), int(mid_y + ny)),
            (int(x2), int(y2)),
            (int(mid_x - nx), int(mid_y - ny)),
        ]
        draw.polygon(pts, outline=GOLD, width=2)

    # Stem
    draw.line([cx, cy + 30, cx, cy + 50], fill=GOLD, width=2)

    # Small circles (berries/flowers)
    for dx, dy in [(-8, -45), (8, -42), (0, -50)]:
        draw.ellipse([cx+dx-4, cy+dy-4, cx+dx+4, cy+dy+4], outline=GOLD2, width=1)


def draw_spa_leaf(draw, cx, cy):
    """SPA / luxury leaf icon."""
    # Large ornamental leaf
    r = 45
    # Outer circle (spa feel)
    draw.ellipse([cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10], outline=GOLD, width=1)

    # Leaf shape
    pts = [
        (cx, cy - 50),
        (cx - 20, cy - 40),
        (cx - 38, cy - 15),
        (cx - 35, cy + 15),
        (cx - 15, cy + 38),
        (cx, cy + 45),
        (cx + 15, cy + 38),
        (cx + 35, cy + 15),
        (cx + 38, cy - 15),
        (cx + 20, cy - 40),
    ]
    draw.polygon(pts, outline=GOLD, width=2)

    # Spiral in center (zen/spa feel)
    for i in range(30):
        t = i / 29 * 3 * math.pi
        rr = 3 + t * 3
        x = cx + int(rr * math.cos(t))
        y = cy + int(rr * math.sin(t))
        if i > 0:
            draw.line([px, py, x, y], fill=GOLD2, width=1)
        px, py = x, y


# --- Procedure definitions ---

PROCEDURES = [
    # Ін'єкційна косметологія — Ботулінотерапія Neuronox
    ("syringe", "Ботулінотерапія 1 зона (Neuronox)", "botox_1z_neuronox", {"zones": 1}),
    ("syringe", "Ботулінотерапія 2 зони (Neuronox)", "botox_2z_neuronox", {"zones": 2}),
    ("syringe", "Ботулінотерапія 3 зони (Neuronox)", "botox_3z_neuronox", {"zones": 3}),
    ("face_syringe", "Ботулінотерапія Full Face (Neuronox)", "botox_ff_neuronox", {}),
    ("nefertiti", "Ліфтинг Ніфертіті (Neuronox)", "nefertiti_neuronox", {}),

    # Ботулінотерапія Xeomin
    ("syringe", "Ботулінотерапія 1 зона (Xeomin)", "botox_1z_xeomin", {"zones": 1}),
    ("syringe", "Ботулінотерапія 2 зони (Xeomin)", "botox_2z_xeomin", {"zones": 2}),
    ("syringe", "Ботулінотерапія 3 зони (Xeomin)", "botox_3z_xeomin", {"zones": 3}),
    ("face_syringe", "Ботулінотерапія Full Face (Xeomin)", "botox_ff_xeomin", {}),
    ("nefertiti", "Ліфтинг Ніфертіті (Xeomin)", "nefertiti_xeomin", {}),

    # Контурна пластика
    ("lips", "Контурна пластика Neuramis Deep", "kontur_neuramis", {"variant": 0}),
    ("lips", "Контурна пластика Saypha Filler", "kontur_saypha", {"variant": 1}),
    ("lips", "Контурна пластика Perfecta", "kontur_perfecta", {"variant": 2}),
    ("lips", "Контурна пластика Genyal / Xcelence 3", "kontur_genyal", {"variant": 0}),

    # Мезо / Біоревіталізація
    ("hair", "Мезотерапія Hair Loss / Hair Vital", "mezo_hair", {}),
    ("droplet", "Біоревіталізація Skin Booster", "biorevit_skinbooster", {}),
    ("eye", "Біоревіталізація Vitaran Tox & Eye", "biorevit_vitaran_eye", {}),

    # Доглядові процедури
    ("leaf", "KEMIKUM", "kemikum", {}),
    ("leaf_needle", "KEMIKUM + мікронідлінг", "kemikum_microneedling", {}),
    ("flask", "PRX-T33", "prx_t33", {}),
    ("flask_needle", "PRX-T33 + мікронідлінг", "prx_t33_microneedling", {}),
    ("botanical", "Азелаїновий / Мигдальний / Феруловий", "acid_peeling", {}),
    ("spa", "SPA-догляд від Christina", "spa_christina", {}),
]


def draw_syringe_icon(draw, cx, cy, zones=1):
    """Syringe with optional zone indicators."""
    draw_syringe(draw, cx, cy, scale=1.0)
    # Zone indicator — small dots on the left
    if zones > 1:
        for i in range(zones):
            dy = cy - 20 + i * 18
            draw.ellipse([cx - 40, dy - 3, cx - 34, dy + 3], fill=GOLD2)


def generate_all():
    print(f"Generating {len(PROCEDURES)} icons to {OUT_DIR}/\n")

    for icon_type, label, filename, params in PROCEDURES:
        img, draw = new_icon()

        if icon_type == "syringe":
            draw_syringe_icon(draw, CX, CY, zones=params.get("zones", 1))
        elif icon_type == "face_syringe":
            draw_face_with_syringe(draw, CX, CY)
        elif icon_type == "nefertiti":
            draw_face_profile_lift(draw, CX, CY)
        elif icon_type == "lips":
            draw_lips(draw, CX, CY, variant=params.get("variant", 0))
        elif icon_type == "hair":
            draw_hair_scalp(draw, CX, CY)
        elif icon_type == "droplet":
            draw_droplet_skin(draw, CX, CY)
        elif icon_type == "eye":
            draw_eye(draw, CX, CY)
        elif icon_type == "leaf":
            draw_leaf(draw, CX, CY, with_needle=False)
        elif icon_type == "leaf_needle":
            draw_leaf(draw, CX, CY - 5, with_needle=True)
        elif icon_type == "flask":
            draw_flask(draw, CX, CY, with_needle=False)
        elif icon_type == "flask_needle":
            draw_flask(draw, CX - 15, CY, with_needle=True)
        elif icon_type == "botanical":
            draw_botanical(draw, CX, CY)
        elif icon_type == "spa":
            draw_spa_leaf(draw, CX, CY)

        draw_label(draw, label)
        save_icon(img, f"{filename}.png")

    print(f"\nDone! {len(PROCEDURES)} icons saved to {OUT_DIR}/")


if __name__ == "__main__":
    generate_all()
