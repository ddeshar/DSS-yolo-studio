# Studio — YOLO Dataset Pipeline

Download images, clean them, and import into Label Studio for annotation.

## Quick Start (Copy-Paste Commands)

Use this section if you only want to run your trained model quickly.

```bash
pip install -r requirements.txt

# 1) Run with YOLO CLI (no custom Python code)
yolo predict model=model/my_model.pt source=0 conf=0.25 show=True

# If camera 0 does not work, try camera 1
yolo predict model=model/my_model.pt source=1 conf=0.25 show=True

# 2) Open browser-based viewer (uses same .env)
python webcam_detect_browser.py
# then open http://127.0.0.1:7860
```

## Folder Structure

```
Studio/
├── config/
│   └── classes.json          # search keywords & per-source limits
├── data/
│   ├── raw/                  # downloaded images (intermediate)
│   └── clean/                # cleaned images (used by Label Studio)
├── docker-compose.yml        # Label Studio container
├── download.sh               # image download + cleaning script
├── labelstudio_import.py     # import tasks into Label Studio
├── requirements.txt          # Python dependencies
└── readme.md
```

---

## 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs: `icrawler`, `duckduckgo-search`, `pillow`, `tqdm`, `requests`
plus `ultralytics`, `opencv-python`, `python-dotenv`, and `flask`.

---

## 2. Configure Classes

Edit `config/classes.json` to define what to download:

```json
[
  {
    "name": "dog",
    "keywords": [
      "dog",
      "dog sitting",
      "dog running",
      "golden retriever",
      "labrador dog"
    ],
    "sources": {
      "bing": 120,
      "duckduckgo": 80
    }
  }
]
```

| Field | Description |
|-------|-------------|
| `name` | Class label (creates a folder under `data/raw/<name>` and `data/clean/<name>`) |
| `keywords` | Search queries — more variety = better dataset |
| `sources.bing` | Max images per keyword from Bing |
| `sources.duckduckgo` | Max images per keyword from DuckDuckGo |

Add multiple objects to the array for multi-class datasets.

---

## 3. Download & Clean Images

```bash
chmod +x download.sh
./download.sh
```

This will:
1. Search Bing and DuckDuckGo for each keyword
2. Save raw images to `data/raw/<class>/`
3. Clean images (remove < 200px, convert to RGB JPEG)
4. Save cleaned images to `data/clean/<class>/`

---

## 4. Start Label Studio

```bash
docker compose up -d
```

Open **http://localhost:8080** in your browser.

### First-time setup

1. Create an account (email + password)
2. Create a new project
3. In project **Settings → Labeling Interface**, use this template:

```xml
<View>
  <Image name="image" value="$image"/>
  <RectangleLabels name="label" toName="image">
    <Label value="dog" background="#FFA39E"/>
  </RectangleLabels>
</View>
```

Replace `dog` with your class name(s). Add more `<Label>` tags for multi-class.

---

## 5. Get Your API Token

1. In Label Studio, click your **profile icon** (top-right) → **Account & Settings**
2. Copy the **Access Token** (it's a long JWT string)
3. Open `labelstudio_import.py` and paste it as `REFRESH_TOKEN`:

```python
REFRESH_TOKEN = "paste-your-token-here"
```

Also update `PROJECT_ID` if your project is not `1` (check the URL: `/projects/<id>/`).

---

## 6. Import Images into Label Studio

You have **two modes**:

### Option A: Local storage (fast, default)

```bash
python3 labelstudio_import.py
```

- Fast — only creates task references, images stay on disk
- Export gives **labels only** (use "YOLO" format)
- You combine labels + images yourself (see step 9)

### Option B: Direct upload (slower, but export includes images)

```bash
python3 labelstudio_import.py --upload
```

- Uploads every image file to Label Studio
- Export with **"YOLO with Images"** gives you a ready-to-train zip
- Slower for large datasets

Expected output:
```
✅ Access token obtained
✅ Authenticated as you@email.com
✅ Local storage already exists (id=1)
📦 Importing 95 tasks to project 1...
✅ Done — 95 tasks imported
```

---

## 7. Start Labeling

Go to **http://localhost:8080** → open your project → click a task → draw bounding boxes.

---

## 8. Export Annotations

Once labeling is done:

1. In Label Studio, go to your project
2. Click **Export**
3. Choose format based on how you imported:

| Import mode | Export format | What you get |
|-------------|--------------|--------------|
| `python3 labelstudio_import.py` (default) | **YOLO** | Labels only (.txt files) |
| `python3 labelstudio_import.py --upload` | **YOLO with Images** | Labels + images in one zip |

4. Download the `.zip` file

---

## 9. Prepare YOLO Training Dataset

After exporting, combine your images + labels into the YOLO training structure:

```bash
# Unzip the export
unzip project-1-at-*.zip -d exported_labels

# Create YOLO dataset structure
mkdir -p dataset/images/train dataset/labels/train

# Copy images
cp data/clean/dog/*.jpg dataset/images/train/

# Copy labels (exported .txt files)
cp exported_labels/labels/*.txt dataset/labels/train/
```

Create a `dataset/data.yaml` file:

```yaml
path: ./dataset
train: images/train
val: images/train  # split later for production

names:
  0: dog
```

Then train with:

```bash
pip install ultralytics
yolo detect train data=dataset/data.yaml model=yolov8n.pt epochs=50 imgsz=640
```

---

## 10. Run Trained Model with YOLO CLI (No Python Code)

After training (or after you already have your weights), run inference directly from terminal.

### Webcam (live)

```bash
yolo predict model=model/my_model.pt source=0 conf=0.25 show=True
```

If camera `0` does not work, try `1` or `2`:

```bash
yolo predict model=model/my_model.pt source=1 conf=0.25 show=True
```

### Single image

```bash
yolo predict model=model/my_model.pt source=path/to/image.jpg conf=0.25 save=True
```

### Video file

```bash
yolo predict model=model/my_model.pt source=path/to/video.mp4 conf=0.25 save=True
```

### Folder of images

```bash
yolo predict model=model/my_model.pt source=path/to/images_folder conf=0.25 save=True
```

Results are saved under `runs/detect/predict*`.

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `./download.sh` | Download + clean images |
| `docker compose up -d` | Start Label Studio |
| `docker compose down` | Stop Label Studio |
| `python3 labelstudio_import.py` | Import via local storage (fast, labels-only export) |
| `python3 labelstudio_import.py --upload` | Upload images directly (export includes images) |
| `yolo predict model=model/my_model.pt source=0 conf=0.25 show=True` | Run webcam inference without writing Python code |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named 'icrawler'` | Run `pip install -r requirements.txt` |
| `zsh: command not found: yolo` | Run `pip install ultralytics` and restart terminal |
| `FileNotFoundError` for model path | Confirm model exists at `model/my_model.pt` or update the command path |
| Webcam opens but no frames / camera error | Try `source=0`, `source=1`, or `source=2`, and allow camera permissions for Terminal/VS Code in macOS |
| Images not loading in Label Studio | The import script auto-creates local storage. Re-run `python3 labelstudio_import.py` |
| `Token refresh failed: 401` | Your token expired. Get a new one from Label Studio UI (step 5) |
| Docker subnet error | Already handled — `network_mode: bridge` is set in docker-compose.yml |
| Download script hangs | Some keywords get throttled. Wait or reduce limits in `classes.json` |
