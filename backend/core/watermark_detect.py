"""
Detect watermarks in video frames.
Watermarks are typically static semi-transparent overlays (logos, text)
that persist across frames in consistent positions (corners, edges).
"""
import cv2
import numpy as np


# Regions to check: (name, y_start%, y_end%, x_start%, x_end%)
# Focus on center area where podcast watermarks typically appear
_CHECK_REGIONS = [
    ("center",       0.35, 0.65, 0.25, 0.75),
    ("upper-center", 0.20, 0.40, 0.25, 0.75),
    ("lower-center", 0.60, 0.80, 0.25, 0.75),
]


def detect_watermark(video_path: str, sample_count: int = 8, threshold: float = 0.90) -> bool:
    """
    Detect if a video has a visible watermark by comparing corner regions
    across multiple frames. Watermarks stay static while video content changes.

    Returns True if watermark detected, False otherwise.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if total_frames < sample_count * 2:
        cap.release()
        return False

    # Sample frames spread across the video (skip first/last 10%)
    sample_positions = [
        int(total_frames * (0.1 + 0.8 * i / (sample_count - 1)))
        for i in range(sample_count)
    ]

    # Extract corner patches from each sampled frame
    corner_patches = {name: [] for name, *_ in _CHECK_REGIONS}

    for pos in sample_positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        for name, y1p, y2p, x1p, x2p in _CHECK_REGIONS:
            y1, y2 = int(frame_h * y1p), int(frame_h * y2p)
            x1, x2 = int(frame_w * x1p), int(frame_w * x2p)
            patch = gray[y1:y2, x1:x2]
            corner_patches[name].append(patch)

    cap.release()

    # Compare patches across frames — watermarks create high similarity
    for name, patches in corner_patches.items():
        if len(patches) < 3:
            continue

        # Compare each patch to the first one using structural similarity
        ref = patches[0].astype(np.float32)
        similarities = []

        for patch in patches[1:]:
            p = patch.astype(np.float32)
            # Normalized cross-correlation
            if ref.std() < 1 or p.std() < 1:
                # Near-uniform region (dark corner etc.) — not a watermark
                similarities.append(0.0)
                continue
            corr = np.corrcoef(ref.flatten(), p.flatten())[0, 1]
            similarities.append(corr if not np.isnan(corr) else 0.0)

        if not similarities:
            continue

        avg_sim = np.mean(similarities)

        # High similarity + non-uniform = static overlay = watermark
        ref_std = ref.std()
        if avg_sim > threshold and ref_std > 15:
            print(f"[watermark] Detected in {name}: similarity={avg_sim:.3f}, detail={ref_std:.1f}")
            return True

    print("[watermark] No watermark detected")
    return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = detect_watermark(sys.argv[1])
        print(f"Watermark: {'YES' if result else 'NO'}")
