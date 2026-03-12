import cv2
import numpy as np
import os
import subprocess
from core.config import VIDEO_ENCODER_ARGS

def _find_face_in_frame(face_cascade, frame, frame_width):
    """Try to detect a face and return center_x, or None if no face found."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    
    faces = face_cascade.detectMultiScale(
        gray, 
        scaleFactor=1.05,
        minNeighbors=3,
        minSize=(40, 40)
    )
    
    if len(faces) > 0:
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest_face
        return x + w // 2
    return None

def track_and_crop_faces(input_video_path: str, output_video_path: str, target_ratio=9/16):
    """
    Reads the input video, uses OpenCV Haar Cascade to track the main speaker's face,
    and crops the 16:9 video frame dynamically into a 9:16 aspect ratio centered
    on the speaker.
    Uses OpenCV VideoWriter for reliable Windows compatibility, then FFmpeg for
    high-quality re-encode + audio merge.
    """
    print(f"Tracking faces and cropping {input_video_path}...")
    
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)

    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        print(f"Error opening video stream or file {input_video_path}")
        return False

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(round(cap.get(cv2.CAP_PROP_FPS)))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    target_width = int(frame_height * target_ratio)
    target_height = frame_height

    if target_width > frame_width:
        target_width = frame_width

    # ===== STEP 1: SCAN FIRST 30 FRAMES TO LOCATE THE FACE =====
    print("Scanning first frames to locate the speaker's face...")
    initial_center_x = frame_width // 2
    
    for scan_i in range(min(30, total_frames)):
        ret, scan_frame = cap.read()
        if not ret:
            break
        face_x = _find_face_in_frame(face_cascade, scan_frame, frame_width)
        if face_x is not None:
            initial_center_x = face_x
            print(f"  -> Face found at frame {scan_i}, center_x={face_x}")
            break
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    smoothed_center_x = initial_center_x

    # ===== STEP 2: CROP FRAMES WITH OPENCV (reliable on Windows) =====
    # Write to AVI with raw codec for lossless intermediate (avoids mp4v quality loss)
    raw_temp_path = os.path.normpath(output_video_path.replace('.mp4', '_raw.avi'))
    fourcc = cv2.VideoWriter_fourcc(*'HFYU')  # HuffYUV = lossless
    out = cv2.VideoWriter(raw_temp_path, fourcc, fps, (target_width, target_height))
    
    if not out.isOpened():
        # Fallback to mp4v if HuffYUV not available
        print("HuffYUV not available, falling back to FFV1...")
        fourcc = cv2.VideoWriter_fourcc(*'FFV1')
        raw_temp_path = os.path.normpath(output_video_path.replace('.mp4', '_raw.avi'))
        out = cv2.VideoWriter(raw_temp_path, fourcc, fps, (target_width, target_height))
    
    if not out.isOpened():
        # Final fallback
        print("FFV1 not available, falling back to mp4v...")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        raw_temp_path = os.path.normpath(output_video_path.replace('.mp4', '_raw.mp4'))
        out = cv2.VideoWriter(raw_temp_path, fourcc, fps, (target_width, target_height))

    # Spring-damper camera system — simulates a physical camera operator.
    # Unlike simple lerp, this has velocity/momentum: the camera accelerates
    # toward the face and decelerates naturally, with a subtle cinematic overshoot.
    SPRING  = 0.06   # stiffness: how strongly camera pulls toward the target
    DAMPING = 0.80   # velocity retention per frame (higher = more momentum/overshoot)
    DEADZONE = 25    # px: ignore face jitter smaller than this

    target_x  = float(initial_center_x)
    camera_x  = float(initial_center_x)
    velocity  = 0.0
    last_detected_x = float(initial_center_x)

    frames_processed = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Detect face every 4 frames (more responsive than 8)
        if frames_processed % 4 == 0:
            face_x = _find_face_in_frame(face_cascade, frame, frame_width)
            if face_x is not None and abs(face_x - last_detected_x) > DEADZONE:
                last_detected_x = face_x
                target_x = float(face_x)

        # Spring force pulls camera toward target; damping bleeds off velocity
        force     = (target_x - camera_x) * SPRING
        velocity  = velocity * DAMPING + force
        camera_x += velocity

        # Clamp so the crop window never goes out of frame
        camera_x = float(np.clip(camera_x, target_width // 2, frame_width - target_width // 2))
        smoothed_center_x = int(camera_x)

        cropped_frame = frame[0:target_height, start_x:end_x]
        cropped_frame = cv2.resize(cropped_frame, (target_width, target_height))
        
        out.write(cropped_frame)

        frames_processed += 1
        if frames_processed % 100 == 0:
            print(f"Processed {frames_processed}/{total_frames} frames")

    cap.release()
    out.release()

    print(f"Cropping done ({frames_processed} frames). Re-encoding with FFmpeg...")
    
    # ===== STEP 3: RE-ENCODE + MERGE AUDIO with FFmpeg (high quality) =====
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", raw_temp_path,        # cropped video (lossless)
            "-i", input_video_path,      # original (for audio)
            *VIDEO_ENCODER_ARGS,
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_video_path
        ]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, check=True)
        
        # Cleanup temp file
        if os.path.exists(raw_temp_path):
            os.remove(raw_temp_path)
            
        print(f"Final video saved at {output_video_path}")
        return True
        
    except Exception as e:
        print(f"Error in FFmpeg re-encode: {e}")
        if os.path.exists(raw_temp_path):
            os.rename(raw_temp_path, output_video_path)
            print(f"Saved raw cropped video at {output_video_path}")
            return True
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        track_and_crop_faces(sys.argv[1], "output_test.mp4")
