# 360° Panorama Building Detection

## Simple Workflow

### Step 1: Run Detection
```bash
python detect.py
```

This will:
- Load your panorama image
- Send it to Gemini AI with the prompt
- Display AI's response

### Step 2: View Panorama
```bash
python server.py
```

Then open: http://localhost:8000/viewer.html

### Configuration

Edit `detect.py` to change:
- `PANORAMA_IMAGE` - path to your panorama
- `PROMPT` - detection prompt

Edit `viewer.html` to change:
- `PANORAMA_IMAGE` - same image path

## Files

- `detect.py` - AI detection script
- `viewer.html` - 360° panorama viewer (preserves original resolution)
- `server.py` - Local web server
- `.env` - API key (GOOGLE_API_KEY)
