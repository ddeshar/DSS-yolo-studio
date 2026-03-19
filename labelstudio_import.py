import requests
import os
import sys
import json
import argparse

# ---- CONFIG ----
LABEL_STUDIO_URL = "http://localhost:8080"
PROJECT_ID = 1
DATA_DIR   = "data/clean"

# JWT refresh token from Label Studio UI (Account & Settings → Access Token)
REFRESH_TOKEN = "YOUR_REFRESH_TOKEN_HERE"

# Path inside the container where files are mounted (must match docker-compose volume)
CONTAINER_FILES_ROOT = "/label-studio/files"

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def get_access_token(base_url, refresh_token):
    """Exchange a JWT refresh token for a short-lived access token."""
    resp = requests.post(
        f"{base_url}/api/token/refresh",
        json={"refresh": refresh_token},
    )
    if resp.status_code != 200:
        print(f"❌ Token refresh failed: {resp.status_code}")
        print(resp.text[:300])
        sys.exit(1)
    access = resp.json()["access"]
    print("✅ Access token obtained")
    return access


def ensure_local_storage(base_url, headers, project_id, storage_path):
    """Create a Local File Storage if one doesn't already exist for this path."""
    resp = requests.get(
        f"{base_url}/api/storages/localfiles?project={project_id}",
        headers=headers,
    )
    if resp.status_code == 200:
        for s in resp.json():
            if s.get("path") == storage_path:
                print(f"✅ Local storage already exists (id={s['id']})")
                return

    resp = requests.post(
        f"{base_url}/api/storages/localfiles",
        headers=headers,
        json={
            "project": project_id,
            "path": storage_path,
            "regex_filter": r".*\.(jpg|jpeg|png|bmp|webp)$",
            "use_blob_urls": True,
            "title": os.path.basename(storage_path),
        },
    )
    if resp.status_code in (200, 201):
        print(f"✅ Local storage created for {storage_path}")
    else:
        print(f"⚠️  Storage creation failed ({resp.status_code}): {resp.text[:200]}")


def import_local_storage(base_url, headers, project_id, data_dir):
    """Import using local file storage references (fast, but export won't include images)."""
    tasks = []

    for cls in sorted(os.listdir(data_dir)):
        class_dir = os.path.join(data_dir, cls)
        if not os.path.isdir(class_dir):
            continue

        ensure_local_storage(
            base_url, headers, project_id,
            f"{CONTAINER_FILES_ROOT}/{cls}",
        )

        for img in sorted(os.listdir(class_dir)):
            if os.path.splitext(img)[1].lower() not in VALID_EXTENSIONS:
                continue
            tasks.append({
                "data": {"image": f"/data/local-files/?d={cls}/{img}"}
            })

    return tasks


def import_upload(base_url, headers, project_id, data_dir):
    """Upload images directly to Label Studio (slower, but export includes images)."""
    uploaded = 0

    for cls in sorted(os.listdir(data_dir)):
        class_dir = os.path.join(data_dir, cls)
        if not os.path.isdir(class_dir):
            continue

        images = [
            f for f in sorted(os.listdir(class_dir))
            if os.path.splitext(f)[1].lower() in VALID_EXTENSIONS
        ]

        print(f"📤 Uploading {len(images)} images from {cls}/...")

        for img in images:
            img_path = os.path.join(class_dir, img)
            with open(img_path, "rb") as f:
                resp = requests.post(
                    f"{base_url}/api/projects/{project_id}/import",
                    headers=headers,
                    files={"file": (img, f, "image/jpeg")},
                )
            if resp.status_code in (200, 201):
                uploaded += 1
            else:
                print(f"  ⚠️  Failed {img}: {resp.status_code}")

            if uploaded % 20 == 0 and uploaded > 0:
                print(f"  ... {uploaded} uploaded")

    print(f"✅ Done — {uploaded} images uploaded directly")
    return None  # no batch import needed


# ---- MAIN ----
parser = argparse.ArgumentParser(description="Import images into Label Studio")
parser.add_argument(
    "--upload", action="store_true",
    help="Upload images directly (enables 'YOLO with Images' export). "
         "Without this flag, uses fast local file storage references.",
)
args = parser.parse_args()

access_token = get_access_token(LABEL_STUDIO_URL, REFRESH_TOKEN)
headers = {"Authorization": f"Bearer {access_token}"}

# Verify auth
me = requests.get(f"{LABEL_STUDIO_URL}/api/current-user/whoami", headers=headers)
if me.status_code != 200:
    print(f"❌ Auth failed: {me.status_code}")
    sys.exit(1)
print(f"✅ Authenticated as {me.json().get('email')}")

if args.upload:
    print("📤 Mode: direct upload (export will include images)")
    import_upload(LABEL_STUDIO_URL, headers, PROJECT_ID, DATA_DIR)
else:
    print("📁 Mode: local file storage (fast, export labels only)")
    tasks = import_local_storage(LABEL_STUDIO_URL, headers, PROJECT_ID, DATA_DIR)

    if not tasks:
        print("❌ No images found in", DATA_DIR)
        sys.exit(1)

    print(f"📦 Importing {len(tasks)} tasks to project {PROJECT_ID}...")

    resp = requests.post(
        f"{LABEL_STUDIO_URL}/api/projects/{PROJECT_ID}/import",
        headers=headers,
        json=tasks,
    )

    if resp.status_code in (200, 201):
        print(f"✅ Done — {len(tasks)} tasks imported")
    else:
        print(f"❌ Import failed: {resp.status_code}")
        print(resp.text[:500])