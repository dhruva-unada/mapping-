"""
Reusable Building Detection Module for 360° Panoramas
"""

from google import genai
from google.genai import types
import PIL.Image
import os
import re
import json
from dotenv import load_dotenv

# Allow loading huge images
PIL.Image.MAX_IMAGE_PIXELS = None

# Load API key from .env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Initialize client
client = genai.Client(api_key=GOOGLE_API_KEY)

def analyze_panorama(image_path, prompt_text, output_json_path=None):
    """
    Analyzes a panorama image to detect buildings based on the prompt.
    Returns a list of building dictionaries.
    Optional: Saves to output_json_path if provided.
    """
    print(f"📸 Analyzing: {image_path}")
    
    try:
        img = PIL.Image.open(image_path)
        
        # Resize for AI (speeds up upload and processing significantly)
        ai_img = img.copy()
        ai_img.thumbnail((2048, 2048))
        print(f"   Resized for AI: {ai_img.size}")
        
    except Exception as e:
        print(f"❌ Error loading image: {e}")
        return []

    print(f"🤖 Running AI detection...")
    
    try:
        response = client.models.generate_content(
            model='gemini-3-pro-image-preview', # Using smaller/faster model if available, or fallback
            contents=[prompt_text, ai_img]
        )
    except Exception as e:
        # Fallback or error handling
        print(f"❌ AI Error (trying backup model): {e}")
        try:
             response = client.models.generate_content(
                model='gemini-3-pro-preview',
                contents=[prompt_text, ai_img]
            )
        except Exception as e2:
             print(f"❌ AI Error 2: {e2}")
             return []

    text_response = ""
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                text_response += part.text

    if not text_response:
        print("⚠️ No response from AI.")
        return []

    # Matches [y, x]
    point_pattern = r'\[\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\]'
    matches = re.findall(point_pattern, text_response)
    
    buildings_data = []
    
    if matches:
        print(f"📍 Found {len(matches)} building points.")
        
        # Parse points
        points = []
        for y_str, x_str in matches:
            try:
                points.append((float(y_str), float(x_str)))
            except ValueError:
                continue
                
        # Sort by x (Left to Right)
        points.sort(key=lambda p: p[1])
        
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        for i, (norm_y, norm_x) in enumerate(points):
            if i < 26:
                label_text = alphabet[i]
            else:
                label_text = alphabet[(i // 26) - 1] + alphabet[i % 26]
            
            # Convert 0-1000 range to Yaw/Pitch
            # Yaw: -180 to 180
            yaw = (norm_x / 1000.0) * 360.0 - 180.0
            
            # Pitch: 90 (up) to -90 (down)
            # 0 on image = top = 90 deg pitch
            # 1000 on image = bottom = -90 deg pitch
            pitch = 90.0 - (norm_y / 1000.0) * 180.0
            
            buildings_data.append({
                "id": str(i),
                "label": label_text,
                "yaw": round(yaw, 2),
                "pitch": round(pitch, 2),
                "y_norm": norm_y, 
                "x_norm": norm_x
            })

        if output_json_path:
            with open(output_json_path, "w") as f:
                json.dump(buildings_data, f, indent=2)
            print(f"💾 Saved data to: {output_json_path}")
            
    else:
        print("\n⚠️ No structured points found in text response.")

    return buildings_data

if __name__ == "__main__":
    # Test block
    img_path = r"C:\Users\159dh\Downloads\DroneViews\DroneViews\Ample-FrontSide\0031_D.jpg" # Example default
    if os.path.exists("panorama_clean.jpg"):
        img_path = "panorama_clean.jpg"
    
    PROMPT = """ROLE: You are an Intelligent 360° Panorama Analyzer with strict De-duplication Logic.
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
Sort by x (ascending).    """    
    
    # PROMPT = """
    # ROLE: You are a High-Precision Computer Vision Surveyor specializing in Equirectangular (360°) Imagery.
    # TASK: Detect all distinct buildings in the panorama and return their exact Center-of-Mass coordinates.

    # CRITICAL FAILURE AVOIDANCE (THE SKYLINE TRAP):
    # THE PROBLEM: Previous detections have drifted into the sky/clouds.
    # THE FIX: You must strictly adhere to the "Texture Lock" rule. The coordinate point MUST land on physical building material.
    # CONSTRAINT: If a coordinate is placed on the sky, it is invalid. Lower the Y-coordinate until it hits the structural center of the visible facade.

    # OPERATIONAL RULES:
    # 1. PRECISE COORDINATE PLACEMENT (The "Bullseye" Logic):
    #    - Vertical: Do NOT target the roof. Target the geometric center of the visible vertical wall.
    #    - Visual Check: The point must be surrounded by windows or walls on all sides.
    #    - Sky Buffer: The point must be at least 20% below the roofline.
    #    - Texture Verification: Ask yourself: "Is this point touching a cloud or a wall?" If cloud -> Move Down.

    # 2. SMART GROUPING & SEPARATION:
    #    - Podium Rule: If multiple towers rise from a shared base, treat them as ONE complex.
    #    - Separation Rule: If there is visible sky separation, label as separate buildings.

    # 3. STRICT EXCLUSION ZONES:
    #    - Ignore: Construction sheds, walls, parking lots, pavements.
    #    - Ignore: The Sky (0% tolerance).
    #    - Ignore: The Ground.

    # OUTPUT FORMAT:
    # Return a strict JSON Array of objects.
    #    - point: [y, x] (Normalized 0-1000).
    #    - Sort by x (ascending).
    # """    
    print("Running test detection...")
    data = analyze_panorama(img_path, PROMPT, "buildings.json")
    print(f"Result: {len(data)} buildings.")
