import cv2
import numpy as np
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

def _find_font(size: int) -> ImageFont.FreeTypeFont:
    """Find a bold system font, fallback gracefully."""
    candidates = [
        "C:/Windows/Fonts/impact.ttf",       # Impact — classic clickbait font
        "C:/Windows/Fonts/arialbd.ttf",       # Arial Bold
        "C:/Windows/Fonts/calibrib.ttf",      # Calibri Bold
    ]
    for path in candidates:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    # Ultimate fallback
    return ImageFont.load_default()


WATERMARK_TEXT = "KlipNyimak"


def _draw_watermark(frame: np.ndarray, text: str = None) -> np.ndarray:
    """
    Draw a semi-transparent watermark in the upper-middle area of the thumbnail.
    Clean, minimal look — white text with subtle shadow, no bar.
    """
    if text is None:
        text = WATERMARK_TEXT

    h, w = frame.shape[:2]
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    overlay = Image.new("RGBA", pil_img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    font_size = int(w * 0.055)
    font = _find_font(font_size)

    bbox = overlay_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]

    # Position: centered horizontally, ~20% from top (upper-middle)
    tx = (w - text_w) // 2
    ty = int(h * 0.18)

    overlay_draw.text(
        (tx, ty), text, font=font,
        fill=(255, 255, 255, 190),
        stroke_width=2,
        stroke_fill=(0, 0, 0, 160),
    )

    pil_img = pil_img.convert("RGBA")
    pil_img = Image.alpha_composite(pil_img, overlay)
    pil_img = pil_img.convert("RGB")

    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def _draw_hook_text(frame: np.ndarray, text: str) -> np.ndarray:
    """
    Draw bold clickbait text on the thumbnail using Pillow.
    Yellow/white text with thick black stroke, positioned at the bottom.
    """
    h, w = frame.shape[:2]

    # Convert BGR (OpenCV) → RGB (Pillow)
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    # Scale font to image width — aim for text to span ~85% of width
    font_size = int(w * 0.09)
    font = _find_font(font_size)

    # Word-wrap text to fit within 85% of width
    max_text_w = int(w * 0.85)
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_text_w and current_line:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test
    if current_line:
        lines.append(current_line)

    # Measure total text block height
    line_bboxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_heights = [bb[3] - bb[1] for bb in line_bboxes]
    line_spacing = int(font_size * 0.2)
    total_h = sum(line_heights) + line_spacing * (len(lines) - 1)

    # Position text near the bottom (above the border)
    margin_bottom = int(h * 0.06)
    y = h - total_h - margin_bottom

    stroke_width = max(3, int(font_size * 0.08))

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2

        # Draw text with stroke (outline) — yellow fill, black outline
        draw.text(
            (x, y),
            line,
            font=font,
            fill=(255, 255, 0),         # Yellow text
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0),       # Black outline
        )
        y += line_heights[i] + line_spacing

    # Convert back to BGR (OpenCV)
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


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
    
    # ===== STEP 2: Upscale to minimum 1080x1920 for crisp thumbnails =====
    MIN_W, MIN_H = 1080, 1920
    h, w = best_frame.shape[:2]
    if w < MIN_W or h < MIN_H:
        scale = max(MIN_W / w, MIN_H / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        best_frame = cv2.resize(best_frame, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        print(f"Upscaled thumbnail: {w}x{h} → {new_w}x{new_h}")
    h, w = best_frame.shape[:2]

    # ===== STEP 3: Apply visual enhancements =====
    # 3a. Subtle zoom crop (105% zoom centered)
    zoom = 1.05
    zh, zw = int(h / zoom), int(w / zoom)
    y1 = (h - zh) // 2
    x1 = (w - zw) // 2
    cropped = best_frame[y1:y1+zh, x1:x1+zw]
    best_frame = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LANCZOS4)
    
    # 3b. Boost contrast and saturation for a vibrant look
    lab = cv2.cvtColor(best_frame, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    
    # CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    
    lab = cv2.merge([l_channel, a_channel, b_channel])
    best_frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    # 3c. Boost saturation slightly
    hsv = cv2.cvtColor(best_frame, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.2, 0, 255)  # +20% saturation
    best_frame = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    
    # 3d. Add a subtle dark gradient at bottom (for text readability)
    gradient = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h // 2, h):
        alpha = (y - h // 2) / (h // 2)  # 0 at middle, 1 at bottom
        gradient[y, :] = [0, 0, 0]
        best_frame[y] = cv2.addWeighted(best_frame[y], 1 - alpha * 0.6, gradient[y], alpha * 0.6, 0)
    
    # 3e. Add a thin colored border (brand accent)
    border_color = (0, 200, 255)  # Yellow-orange accent (BGR)
    border_px = max(4, w // 120)
    cv2.rectangle(best_frame, (0, 0), (w-1, h-1), border_color, border_px)
    
    # ===== STEP 4: Watermark at the top =====
    best_frame = _draw_watermark(best_frame)

    # ===== STEP 5: Add text overlay if provided (using Pillow for quality) =====
    if caption_text:
        caption_text = caption_text.upper()
        best_frame = _draw_hook_text(best_frame, caption_text)
    
    # ===== STEP 6: Save =====
    cv2.imwrite(output_path, best_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(f"Thumbnail saved to {output_path}")
    return output_path

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        generate_thumbnail(sys.argv[1], caption_text="VIRAL MOMENT")
