#!/usr/bin/env python3
"""
Upload service icons to WLaunch CRM and assign them to matching services.

Usage:
    python3 upload_icons.py [--dry-run]

Reads icons from wl_icons/, uploads each via WLaunch image API,
then updates the corresponding service with the returned logo URL.

Requires: config.py (WLAUNCH_API_URL, COMPANY_ID), wlaunch_api.py (HEADERS)
Must run from /home/gomoncli/zadarma/ (or adjust sys.path).
"""

import os
import sys
import json
import time
import logging
import requests

# Allow running locally (outside server) — add script dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import WLAUNCH_API_URL, COMPANY_ID
from wlaunch_api import HEADERS, get_branch_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("upload_icons")

ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wl_icons")

# ============================================================
# Mapping: icon filename (without .png) -> WLaunch service/category name
# 63 total: 5 categories + 58 services
# ============================================================

ICON_SERVICE_MAP = {
    # ── Categories (type=GROUP) ──
    "cat_injection":   "Ін'єкційна косметологія",
    "cat_aparatna":    "Апаратна косметологія",
    "cat_body":        "Догляд за тілом",
    "cat_whitening":   "Відбілювання зубів",
    "cat_care":        "Доглядові процедури",

    # ── Ін'єкційна: Ботулінотерапія Neuronox ──
    "botox_1z_neuronox":  "Ботулінотерапія 1 зона (Neuronox)",
    "botox_2z_neuronox":  "Ботулінотерапія 2 зони (Neuronox)",
    "botox_3z_neuronox":  "Ботулінотерапія 3 зони (Neuronox)",
    "botox_ff_neuronox":  "Ботулінотерапія Full Face (Neuronox)",
    "nefertiti_neuronox": "Ліфтинг Ніфертіті (Neuronox)",

    # ── Ботулінотерапія Xeomin ──
    "botox_1z_xeomin":  "Ботулінотерапія 1 зона (Xeomin)",
    "botox_2z_xeomin":  "Ботулінотерапія 2 зони (Xeomin)",
    "botox_3z_xeomin":  "Ботулінотерапія 3 зони (Xeomin)",
    "botox_ff_xeomin":  "Ботулінотерапія Full Face (Xeomin)",
    "nefertiti_xeomin":  "Ліфтинг Ніфертіті (Xeomin)",

    # ── Гіпергідроз ──
    "hyperhidrosis": "Лікування гіпергідрозу (Botox)",

    # ── Контурна пластика ──
    "kontur_neuramis":      "Контурна пластика Neuramis Deep",
    "kontur_saypha":        "Контурна пластика Saypha Filler",
    "kontur_perfecta":      "Контурна пластика Perfecta",
    "kontur_genyal":        "Контурна пластика Genyal / Xcelence 3",
    "kontur_neauvia_lips":  "Контурна пластика Neauvia Intense Lips",
    "kontur_neuramis_vol":  "Контурна пластика Neuramis Volume",
    "kontur_saypha_vol":    "Контурна пластика Saypha Volume",
    "kontur_neauvia_stim":  "Контурна пластика Neauvia Stimulate",

    # ── Біорепарація ──
    "biorep_rejuran_hb": "Біорепарація Rejuran HB",
    "biorep_rejuran_i":  "Біорепарація Rejuran I",
    "biorep_rejuran_s":  "Біорепарація Rejuran S",
    "biorep_exosomes":   "Біорепарація Екзосоми (Exoxe) 2.5 ml",

    # ── Біоревіталізація ──
    "biorevit_smart":         "Smart-біоревіталізація",
    "biorevit_vitaran_eye":   "Біоревіталізація Vitaran Tox & Eye",
    "biorevit_neauvia_hydro": "Біоревіталізація Neauvia Hydro Deluxe",
    "biorevit_skinbooster":   "Біоревіталізація Skin Booster",

    # ── Мезотерапія ──
    "mezo_hair":          "Мезотерапія Hair Loss / Hair Vital",
    "mezo_fillup":        "Мезотерапія Fill Up",
    "mezo_plinest":       "Мезотерапія Plinest One (4 ml)",
    "mesobotox_monaco":   "Мезоботокс «Монако» (4 ml)",

    # ── Ліполітики ──
    "lipo_face": "Ліполітики (обличчя, 4 мл)",
    "lipo_body": "Ліполітики (тіло, 10 мл)",

    # ── Корекції ──
    "hyaluronidase":      "Гіалуронідаза (розчинення філера)",
    "correction_filler":  "Корекція філера",
    "correction_botox":   "Корекція ботулотоксину",

    # ── Апаратна косметологія ──
    "wow_cleaning":   "WOW-чистка обличчя",
    "wow_glow":       "WOW-чистка «Сяяння»",
    "teen_cleaning":  "Підліткова делікатна чистка",
    "oxygen_glow":    "Кисневий догляд Glow Skin",
    "carboxy":        "Карбокситерапія",

    # ── Доглядові процедури ──
    "kemikum":               "KEMIKUM",
    "kemikum_microneedling": "KEMIKUM + мікронідлінг",
    "prx_t33":               "PRX-T33",
    "prx_t33_microneedling": "PRX-T33 + мікронідлінг",
    "acid_peeling":          "Азелаїновий / Мигдальний / Феруловий",
    "spa_christina":         "SPA-догляд від Christina",

    # ── Догляд за тілом ──
    "body_part_massage":   "Моделювання окремої ділянки",
    "body_full_contour":   "Моделювання всього тіла",
    "body_relax_massage":  "Загальний релакс-масаж всього тіла",
    "pressotherapy":       "Пресотерапія «Легкість тіла»",

    # ── Відбілювання зубів ──
    "whitening_light":    "Відбілювання зубів Light",
    "whitening_medium":   "Відбілювання зубів Medium",
    "whitening_maximum":  "Відбілювання зубів Maximum",

    # ── Top-level ──
    "consultation":         "Консультація",
    "consultation_offline": "Офлайн-консультація",
    "consultation_online":  "Онлайн-консультація",
}


def fetch_all_services():
    """Fetch all services from WLaunch, return dict {name_lower: {id, name}}."""
    url = f"{WLAUNCH_API_URL}/company/{COMPANY_ID}/service"
    all_services = {}
    page = 0

    while page < 10:
        params = {"page": page, "size": 200, "sort": "name"}
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch services page {page}: {e}")
            break

        items = data.get("content", [])
        if not items:
            break

        for s in items:
            name = (s.get("name") or "").strip()
            if name:
                all_services[name.lower()] = {
                    "id": s.get("id"),
                    "name": name,
                    "logo": s.get("logo"),
                }

        total_pages = data.get("page", {}).get("total_pages", 1)
        if page + 1 >= total_pages:
            break
        page += 1

    logger.info(f"Loaded {len(all_services)} services from WLaunch")
    return all_services


def upload_image(filepath):
    """
    Upload image file to WLaunch.
    POST /company/{cid}/image/file?crop=true&x=0&y=0&width=260&height=260
    Returns the image URL or None.
    """
    url = f"{WLAUNCH_API_URL}/company/{COMPANY_ID}/image/file"
    params = {
        "crop": "true",
        "x": 0,
        "y": 0,
        "width": 260,
        "height": 260,
    }

    upload_headers = {
        "Authorization": HEADERS["Authorization"],
        "Accept": "application/json",
    }

    filename = os.path.basename(filepath)
    try:
        with open(filepath, "rb") as f:
            files = {"file": (filename, f, "image/png")}
            resp = requests.post(url, headers=upload_headers, params=params,
                                 files=files, timeout=30)

        if resp.status_code in (200, 201):
            data = resp.json()
            # WLaunch may return URL in different fields
            image_url = (data.get("uri") or data.get("url") or data.get("image_url") or
                         data.get("path") or data.get("link"))
            if not image_url and isinstance(data, str):
                image_url = data
            logger.info(f"Uploaded {filename} -> {image_url}")
            return image_url
        else:
            logger.error(f"Upload failed for {filename}: {resp.status_code} {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Upload error for {filename}: {e}")
        return None


def update_service_logo(service_id, logo_url):
    """
    Update service logo in WLaunch.
    POST /company/{cid}/service/{sid} with {company_service: {logo: url}}
    """
    url = f"{WLAUNCH_API_URL}/company/{COMPANY_ID}/service/{service_id}"
    post_headers = dict(HEADERS)
    post_headers["Content-Type"] = "application/json"

    payload = {
        "company_service": {
            "logo": logo_url
        }
    }

    try:
        resp = requests.post(url, headers=post_headers, json=payload, timeout=15)
        if resp.status_code in (200, 201):
            logger.info(f"Updated service {service_id} logo -> {logo_url}")
            return True
        else:
            logger.error(f"Update failed for {service_id}: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Update error for {service_id}: {e}")
        return False


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        logger.info("=== DRY RUN MODE ===")

    # 1. Fetch all services from WLaunch
    services = fetch_all_services()
    if not services:
        logger.error("No services found in WLaunch!")
        return

    # 2. Process each icon
    uploaded = 0
    updated = 0
    skipped = 0
    errors = 0

    for filename_base, service_name in ICON_SERVICE_MAP.items():
        icon_path = os.path.join(ICONS_DIR, f"{filename_base}.png")

        if not os.path.exists(icon_path):
            logger.warning(f"Icon file not found: {icon_path}")
            errors += 1
            continue

        # Find service in WLaunch
        service_key = service_name.lower()
        service_data = services.get(service_key)

        if not service_data:
            # Try fuzzy match
            for sname, sdata in services.items():
                if service_name.lower() in sname or sname in service_name.lower():
                    service_data = sdata
                    logger.info(f"Fuzzy matched '{service_name}' -> '{sdata['name']}'")
                    break

        if not service_data:
            logger.warning(f"Service not found in WLaunch: '{service_name}'")
            skipped += 1
            continue

        service_id = service_data["id"]
        existing_logo = service_data.get("logo")

        if existing_logo:
            logger.info(f"Service '{service_name}' already has logo: {existing_logo} (will overwrite)")

        if dry_run:
            logger.info(f"[DRY] Would upload {filename_base}.png and set logo for '{service_name}' (id={service_id})")
            continue

        # 3. Upload image
        image_url = upload_image(icon_path)
        if not image_url:
            errors += 1
            continue
        uploaded += 1

        # 4. Update service logo
        if update_service_logo(service_id, image_url):
            updated += 1
        else:
            errors += 1

        # Rate limit: small delay between requests
        time.sleep(0.5)

    # Summary
    logger.info(f"\n{'='*50}")
    logger.info(f"Summary:")
    logger.info(f"  Total icons:    {len(ICON_SERVICE_MAP)}")
    logger.info(f"  Uploaded:       {uploaded}")
    logger.info(f"  Updated:        {updated}")
    logger.info(f"  Skipped:        {skipped}")
    logger.info(f"  Errors:         {errors}")
    if dry_run:
        logger.info(f"  (DRY RUN - no actual changes)")


if __name__ == "__main__":
    main()
