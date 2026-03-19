#!/bin/bash

CONFIG_FILE="config/classes.json"
RAW_DIR="data/raw"
CLEAN_DIR="data/clean"

mkdir -p "$RAW_DIR"
mkdir -p "$CLEAN_DIR"

# ==============================
# CHECKS
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Missing config/classes.json"
    exit 1
fi

echo "🚀 Download + Clean pipeline started..."

# ==============================
python3 <<EOF

import os
import json
import uuid
import shutil
import requests
from tqdm import tqdm
from PIL import Image
from io import BytesIO
from duckduckgo_search import DDGS
from icrawler.builtin import BingImageCrawler

RAW_DIR = "$RAW_DIR"
CLEAN_DIR = "$CLEAN_DIR"

# ---------------- LOAD CONFIG ----------------
with open("$CONFIG_FILE") as f:
    classes = json.load(f)

# ---------------- UTIL ----------------
def save_image(content, folder):
    filename = f"{uuid.uuid4().hex}.jpg"
    path = os.path.join(folder, filename)

    try:
        img = Image.open(BytesIO(content)).convert("RGB")
        img.save(path, "JPEG")
        return True
    except:
        return False

# ---------------- DUCKDUCKGO ----------------
def download_duckduckgo(keyword, limit, folder):
    try:
        with DDGS() as ddgs:
            results = ddgs.images(keyword, max_results=limit)
            for r in results:
                try:
                    img = requests.get(r["image"], timeout=5).content
                    save_image(img, folder)
                except:
                    continue
    except:
        pass

# ---------------- BING ----------------
def download_bing(keyword, limit, folder):
    try:
        crawler = BingImageCrawler(
            feeder_threads=1,
            parser_threads=2,
            downloader_threads=4,
            storage={"root_dir": folder},
        )
        crawler.crawl(keyword=keyword, max_num=limit)
    except:
        pass

# ---------------- CLEANING ----------------
def clean_images(src_dir, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    kept = 0
    removed = 0

    for root, _, files in os.walk(src_dir):
        for f in files:
            path = os.path.join(root, f)

            try:
                img = Image.open(path)

                # remove very small images
                if img.width < 200 or img.height < 200:
                    removed += 1
                    continue

                # save cleaned
                new_path = os.path.join(dst_dir, f"{uuid.uuid4().hex}.jpg")
                img.convert("RGB").save(new_path)

                kept += 1

            except:
                removed += 1

    return kept, removed

# ---------------- MAIN ----------------
for cls in classes:
    name = cls["name"]
    keywords = cls["keywords"]

    # Per-source limits — fall back to equal split of legacy "limit" field
    legacy = cls.get("limit", 100)
    sources = cls.get("sources", {"bing": legacy // 2, "duckduckgo": legacy // 2})
    bing_limit = int(sources.get("bing", 0))
    ddg_limit  = int(sources.get("duckduckgo", 0))

    class_raw = os.path.join(RAW_DIR, name)
    class_clean = os.path.join(CLEAN_DIR, name)

    os.makedirs(class_raw, exist_ok=True)

    total = bing_limit + ddg_limit
    print(f"\\n📦 Class: {name}  (bing={bing_limit}, duckduckgo={ddg_limit}, total per keyword={total})")

    for kw in keywords:
        print(f"  🔍 {kw}")

        for _ in tqdm(range(1), desc=kw, leave=False):
            if bing_limit > 0:
                download_bing(kw, bing_limit, class_raw)
            if ddg_limit > 0:
                download_duckduckgo(kw, ddg_limit, class_raw)

    print("  🧹 Cleaning...")
    kept, removed = clean_images(class_raw, class_clean)

    print(f"  ✅ Cleaned: {kept}, Removed: {removed}")

print("\\n🎯 All classes processed")

EOF