from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import os
import uuid
import json
import shutil
from werkzeug.utils import secure_filename
from detect import analyze_panorama

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['PROCESSED_FOLDER'] = 'static/processed'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024 # 100 MB limit

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/detect', methods=['POST'])
def detect():
    if 'image' not in request.files:
        return redirect(request.url)
    
    file = request.files['image']
    if file.filename == '':
        return redirect(request.url)
    
    file = request.files['image']
    if file.filename == '':
        return redirect(request.url)
    
    # Hardcoded prompt as requested
    prompt = """ROLE: You are an Intelligent 360° Panorama Analyzer with strict De-duplication Logic.
CRITICAL OBJECTIVE: Clean, Minimalist Detection.
The Problem: Previous attempts generated multiple overlapping labels for the same building complex.
The Fix: You must apply a "One Contiguous Structure = One Label" rule.
OPERATIONAL RULES (Strict Constraints):
1. AGGRESSIVE GROUPING (The "Silhouette" Test):
Look at the horizon. If multiple vertical blocks, towers, or wings are connected at the base or visually overlap without clear sky separating them, they are ONE SINGLE BUILDING.
Do NOT label individual towers of the same apartment complex.
Do NOT label the left wing and right wing separately.
ACTION: Calculate the center of the entire connected mass and place ONE point there.
2. HORIZONTAL SPACING (Non-Maximum Suppression):
Constraint: No two labels can be horizontally closer than 5% of the image width (approx. 50 units on x-axis) unless there is a large, visible gap of sky between them.
If you detect two points close together, keep only the one that is strictly on the main central mass and discard the other.
3. PRECISE PLACEMENT (Upper Facade Anchor):
Location: Target the Top 15% of the building's facade.
Texture Lock: The point must be on the wall/windows.
Safety Margin: Drop the point vertically so it is clearly below the roofline.
If touching Sky: INVALID.
If touching Parapet/Roof Edge: INVALID.
If touching High Windows: VALID.
4. EXCLUSIONS:
Ignore all foreground clutter (walls, small sheds, construction debris).
Ignore distant, hazy buildings on the horizon. Focus on the main, clear urban structures.
OUTPUT JSON FORMAT:
Return a valid JSON array of objects.
point: [y, x] (Normalized 0-1000).
y: High on the wall (small number), but strictly > roofline.
x: Center of the entire building complex.
Sort by x (ascending).
"""
#     prompt = """
# ROLE: You are an Advanced Object Detection Model specializing in Dense Urban Panoramas (360° Equirectangular).
# OBJECTIVE: Perform an EXHAUSTIVE detection of every visible building.

# Maximize Recall: Detect every vertical structure, from massive foreground towers to distant skyline blocks. Do not ignore a building just because it is far away or partially obscured.
# Specific Targeting: Place the coordinate point at the TOP OF THE BUILDING, but strictly inside the structure's boundary.

# CRITICAL PLACEMENT RULES (The "Upper Anchor" Logic):
# 1. TARGET: THE "UPPER FACADE ANCHOR"
#    - Vertical Location: You must identify the absolute top edge (roofline/parapet) of the building.
#    - The Safety Drop: Once you find the roofline, drop the point vertically down by 5% to 10%.
#    - Reasoning: The point must rest on the highest row of windows or the top concrete band.
#    - Strict Prohibition: The point must NEVER touch the sky, clouds, or the empty space above the roof. It must touch the building's texture.
#    - Horizontal Location: Center the point horizontally relative to the visible width of that specific building tower.

# 2. HIGH-SENSITIVITY DETECTION (Catch Everything):
#    - Depth Agnostic: Detect buildings in the Foreground (close), Mid-ground, and Background (horizon/skyline).
#    - Occlusion Handling: If a building is partially blocked by another, still detect the visible top portion of the rear building.
#    - Distinct Structures: If a complex has multiple distinct towers of different heights, label the top of EACH distinct tower separately. Do not just label the center of the whole group. Label the peaks.

# 3. EXCLUSIONS:
#    - Do not label trees, cranes, streetlights, or clouds.
#    - Do not label ground-level shacks or boundary walls (height < 3 meters).

# OUTPUT JSON FORMAT:
# Return a valid JSON array. Each object represents a building.
#    - point: [y, x] (Normalized 0-1000).
#    - y: Represents the Upper Facade. Values should be "higher" (smaller numbers) compared to the building's base, but strictly below the roof edge.
#    - x: Horizontal center.
#    - Sort by x (ascending from left 0 to right 1000).

# Example Interpretation:
#    - Bad Point: Touching the blue sky pixels above the roof.
#    - Perfect Point: Touching the logo, the top penthouse window, or the parapet wall just below the sky.

# Output ONLY valid JSON."""


    file_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    # Use ID in filename to avoid collisions but keep extension
    ext = os.path.splitext(filename)[1]
    saved_filename = f"{file_id}{ext}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
    file.save(file_path)

    # Process
    # We copy the image to procssed folder as the "panorama" source for that ID
    processed_img_path = os.path.join(app.config['PROCESSED_FOLDER'], f"{file_id}.jpg")
    shutil.copy(file_path, processed_img_path)
    
    json_path = os.path.join(app.config['PROCESSED_FOLDER'], f"{file_id}.json")
    
    # Run AI
    analyze_panorama(file_path, prompt, json_path)
    
    return redirect(url_for('view_panorama', id=file_id))

@app.route('/view/<id>')
def view_panorama(id):
    return render_template('viewer.html', id=id)

@app.route('/edit/<id>')
def edit_panorama(id):
    return render_template('editor.html', id=id)

@app.route('/api/data/<id>')
def get_data(id):
    json_path = os.path.join(app.config['PROCESSED_FOLDER'], f"{id}.json")
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify([])

@app.route('/api/save/<id>', methods=['POST'])
def save_data(id):
    data = request.json
    json_path = os.path.join(app.config['PROCESSED_FOLDER'], f"{id}.json")
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)
    return jsonify({"status": "success"})

@app.route('/download/<id>')
def download(id):
    # This is a bit complex: we need to generate a standalone HTML file.
    # For now, let's just create a quick "downloadable" HTML string and serve it.
    
    # 1. Read the template
    # 2. Embed the JSON data
    # 3. Read the image (or keep relative link if we zip it, but user wants single file? 
    #    Usually single HTML requires base64 image which is huge).
    #    Alternatively, just serve the current page as "Save" (Ctrl+S).
    
    # Strategy: Render a template that has the JSON embedded directly in a <script> variable
    # instead of fetching it. User can then "Save Page As".
    
    json_path = os.path.join(app.config['PROCESSED_FOLDER'], f"{id}.json")
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            hotspots_data = json.load(f)
    else:
        hotspots_data = []

    return render_template('viewer_standalone.html', 
                          id=id, 
                          hotspots_data=json.dumps(hotspots_data),
                          base_url=request.url_root)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
