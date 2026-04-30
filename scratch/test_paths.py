import os
from config import VIDEOS, BASE_DIR

for i, video in VIDEOS.items():
    photo_path = video.get("photo", "").strip()
    
    current_dir = os.path.dirname(os.path.abspath("handlers/videos.py"))
    # In the real code, __file__ would be handlers/videos.py
    # So current_dir would be .../handlers
    
    # Simulating handlers/videos.py logic:
    # current_dir = os.path.dirname(os.path.abspath(__file__)) # .../handlers
    # root_dir = os.path.dirname(current_dir) # .../
    # abs_path = os.path.join(root_dir, photo_path)
    
    # But since I'm running this from root:
    sim_current_dir = os.path.join(os.getcwd(), "handlers")
    sim_root_dir = os.path.dirname(sim_current_dir)
    sim_abs_path = os.path.join(sim_root_dir, photo_path)
    
    print(f"Video {i}:")
    print(f"  Config photo_path: {photo_path}")
    print(f"  Simulated abs_path: {sim_abs_path}")
    print(f"  Exists: {os.path.exists(sim_abs_path)}")
