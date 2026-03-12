import cv2
import numpy as np
import os
import subprocess

def generate_thumbnail(video_path: str, output_path: str = None, caption_text: str = None) -> str:
    """
    Generates an eye-catching thumbnail from the video.
    - Picks the best frame (face detected, good lighting)
    - Adds contrast boost/vibrance
    - Adds a subtle zoom crop
    - Optionally overlays bold text
    Returns the path to the thumbnail image.
    """
    print(f"Generating thumbnail for {video_path}...")
    
    if output_path is None:
        output_path = video_path.rsplit('.', 1)[0] + '_thumb.jpg'
    
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Could not open video for thumbnail")
        return ""
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # ===== STEP 1: Find the best frame (with a face, good expression) =====
    # Sample frames from the first third of the video (usually best content)
    best_frame = None
    best_face_size = 0
    sample_points = [int(total_frames * p) for p in [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4]]
    
    for frame_idx in sample_points:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3, minSize=(40, 40))
        
        if len(faces) > 0:
            largest = max(faces, key=lambda f: f[2] * f[3])
            face_size = largest[2] * largest[3]
            if face_size > best_face_size:
                best_face_size = face_size
                best_frame = frame.copy()
    
    cap.release()
    
    # Fallback: grab frame at 20% if no face found
    if best_frame is None:
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total_frames * 0.2))
        ret, best_frame = cap.read()
        cap.release()
        if not ret:
            print("Error: Could not read any frame")
            return ""
    
    # ===== STEP 2: Apply visual enhancements =====
    h, w = best_frame.shape[:2]
    
    # 2a. Subtle zoom crop (105% zoom centered)
    zoom = 1.05
    zh, zw = int(h / zoom), int(w / zoom)
    y1 = (h - zh) // 2
    x1 = (w - zw) // 2
    cropped = best_frame[y1:y1+zh, x1:x1+zw]
    best_frame = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LANCZOS4)
    
    # 2b. Boost contrast and saturation for a vibrant look
    # Convert to LAB color space for better contrast adjustment
    lab = cv2.cvtColor(best_frame, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    
    # CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    
    lab = cv2.merge([l_channel, a_channel, b_channel])
    best_frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    # 2c. Boost saturation slightly
    hsv = cv2.cvtColor(best_frame, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.2, 0, 255)  # +20% saturation
    best_frame = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    
    # 2d. Add a subtle dark gradient at bottom (for text readability)
    gradient = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h // 2, h):
        alpha = (y - h // 2) / (h // 2)  # 0 at middle, 1 at bottom
        gradient[y, :] = [0, 0, 0]
        best_frame[y] = cv2.addWeighted(best_frame[y], 1 - alpha * 0.6, gradient[y], alpha * 0.6, 0)
    
    # 2e. Add a thin colored border (brand accent)
    border_color = (0, 200, 255)  # Yellow-orange accent (BGR)
    border_px = max(4, w // 120)
    cv2.rectangle(best_frame, (0, 0), (w-1, h-1), border_color, border_px)
    
    # ===== STEP 3: Add text overlay if provided =====
    if caption_text:
        caption_text = caption_text.upper()
        
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = w / 400  # Scale with video width
        thickness = max(2, int(w / 150))
        
        # Word wrap
        words = caption_text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            text_size = cv2.getTextSize(test_line, font, font_scale, thickness)[0]
            if text_size[0] > w * 0.85:
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
        
        # Draw text from bottom
        line_height = int(cv2.getTextSize("A", font, font_scale, thickness)[0][1] * 1.8)
        start_y = h - border_px - 20 - (len(lines) - 1) * line_height
        
        for i, line in enumerate(lines):
            text_size = cv2.getTextSize(line, font, font_scale, thickness)[0]
            text_x = (w - text_size[0]) // 2  # center
            text_y = start_y + i * line_height
            
            # Black outline
            cv2.putText(best_frame, line, (text_x, text_y), font, font_scale, (0, 0, 0), thickness + 3, cv2.LINE_AA)
            # White text
            cv2.putText(best_frame, line, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    
    # ===== STEP 4: Save =====
    cv2.imwrite(output_path, best_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(f"Thumbnail saved to {output_path}")
    return output_path

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        generate_thumbnail(sys.argv[1], caption_text="VIRAL MOMENT")
