"""Explainable visual descriptors for the Find & Return proof of concept."""

from __future__ import annotations

import cv2
import numpy as np


def decode_image(payload: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("That file could not be read as an image.")
    height, width = image.shape[:2]
    if width < 48 or height < 48:
        raise ValueError("Please use an image at least 48 × 48 pixels.")
    scale = min(1.0, 900 / max(width, height))
    if scale < 1:
        image = cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    return image


def _object_mask(image: np.ndarray) -> np.ndarray:
    """Estimate a centered object against a simple, evenly lit tray background."""
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    border = np.concatenate((hsv[0, :, :], hsv[-1, :, :], hsv[:, 0, :], hsv[:, -1, :]), axis=0)
    background = np.median(border, axis=0)
    delta = hsv.astype(np.float32) - background.astype(np.float32)
    delta[:, :, 0] *= 0.55  # Hue wraps around; saturation/value carry most of the contrast.
    distance = np.linalg.norm(delta, axis=2)
    mask = (distance > 28).astype(np.uint8) * 255
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    fraction = cv2.countNonZero(mask) / float(width * height)
    if fraction < 0.015 or fraction > 0.88:
        # A central crop keeps matching useful when the tray and object have similar colors.
        mask[:] = 0
        cv2.ellipse(mask, (width // 2, height // 2), (int(width * 0.43), int(height * 0.43)), 0, 0, 360, 255, -1)
    return mask


def describe(image: np.ndarray) -> dict[str, object]:
    """Return normalized color, silhouette, and texture descriptors."""
    image = cv2.resize(image, (240, 240), interpolation=cv2.INTER_AREA)
    mask = _object_mask(image)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    color_hist = cv2.calcHist([hsv], [0, 1], mask, [12, 4], [0, 180, 0, 256])
    color_hist = cv2.normalize(color_hist, color_hist).flatten()

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = max(contours, key=cv2.contourArea) if contours else None
    if contour is not None and cv2.contourArea(contour) > 20:
        moments = cv2.moments(contour)
        hu = cv2.HuMoments(moments).flatten()
        hu = [-float(np.sign(v) * np.log10(abs(v) + 1e-12)) for v in hu]
        x, y, w, h = cv2.boundingRect(contour)
        shape = hu + [float(w) / max(h, 1), float(cv2.contourArea(contour)) / max(w * h, 1)]
    else:
        shape = [0.0] * 9

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    texture_hist = cv2.calcHist([gray], [0], mask, [12], [0, 256])
    texture_hist = cv2.normalize(texture_hist, texture_hist).flatten()
    edges = cv2.Canny(gray, 70, 150)
    edge_density = float(cv2.countNonZero(cv2.bitwise_and(edges, edges, mask=mask))) / max(cv2.countNonZero(mask), 1)

    pixels = hsv[mask > 0]
    hue = float(np.median(pixels[:, 0])) if len(pixels) else 0.0
    saturation = float(np.median(pixels[:, 1])) if len(pixels) else 0.0
    color_name = _color_name(hue, saturation)
    return {
        "color": color_hist.astype(float).round(5).tolist(),
        "shape": np.asarray(shape, dtype=float).round(5).tolist(),
        "texture": texture_hist.astype(float).round(5).tolist(),
        "edge_density": round(edge_density, 5),
        "color_name": color_name,
    }


def _color_name(hue: float, saturation: float) -> str:
    if saturation < 36:
        return "white / neutral" if hue == 0 else "neutral"
    if hue < 10 or hue >= 170:
        return "red"
    if hue < 22:
        return "orange"
    if hue < 36:
        return "yellow"
    if hue < 78:
        return "green"
    if hue < 102:
        return "cyan"
    if hue < 135:
        return "blue"
    if hue < 160:
        return "purple"
    return "pink"


def _histogram_similarity(left: list[float], right: list[float]) -> float:
    a = np.asarray(left, dtype=np.float32)
    b = np.asarray(right, dtype=np.float32)
    if a.shape != b.shape or a.size == 0:
        return 0.0
    return float(np.clip(1.0 - cv2.compareHist(a, b, cv2.HISTCMP_BHATTACHARYYA), 0.0, 1.0))


def compare(query: dict[str, object], candidate: dict[str, object]) -> dict[str, int]:
    """Score two item photos, returning human-readable percentages by visual cue."""
    color = _histogram_similarity(query["color"], candidate["color"])
    texture_hist = _histogram_similarity(query["texture"], candidate["texture"])
    texture_edges = 1.0 - min(abs(float(query["edge_density"]) - float(candidate["edge_density"])) * 3.5, 1.0)
    texture = 0.72 * texture_hist + 0.28 * texture_edges

    left_shape = np.asarray(query["shape"], dtype=np.float32)
    right_shape = np.asarray(candidate["shape"], dtype=np.float32)
    shape = 1.0 / (1.0 + float(np.mean(np.abs(left_shape - right_shape))) / 3.0)
    return {
        "color": round(color * 100),
        "shape": round(shape * 100),
        "pattern": round(texture * 100),
        "overall": round((0.45 * color + 0.35 * shape + 0.20 * texture) * 100),
    }


def combine_views(features: list[dict[str, object]]) -> dict[str, object]:
    """Average descriptors from multiple tray angles into one item signature."""
    if len(features) == 1:
        return features[0]
    combined: dict[str, object] = {}
    for name in ("color", "shape", "texture"):
        average = np.mean([np.asarray(row[name], dtype=np.float32) for row in features], axis=0)
        if name in ("color", "texture"):
            average = average / max(float(np.linalg.norm(average)), 1e-12)
        combined[name] = average.round(5).tolist()
    combined["edge_density"] = round(float(np.mean([float(row["edge_density"]) for row in features])), 5)
    names = [str(row["color_name"]) for row in features]
    combined["color_name"] = max(set(names), key=names.count)
    return combined


def demo_photo(kind: str, color: tuple[int, int, int], accent: tuple[int, int, int] | None = None) -> bytes:
    """Create a simple, clearly synthetic sample photo for the local demo registry."""
    image = np.full((420, 420, 3), (237, 235, 228), dtype=np.uint8)
    shadow = np.zeros_like(image)
    accent = accent or tuple(max(0, int(channel * 0.68)) for channel in color)
    if kind == "bottle":
        cv2.ellipse(shadow, (210, 340), (80, 20), 0, 0, 360, (190, 190, 190), -1)
        cv2.rectangle(image, (145, 132), (275, 322), color, -1)
        cv2.ellipse(image, (210, 132), (65, 20), 0, 0, 360, color, -1)
        cv2.rectangle(image, (177, 92), (243, 135), accent, -1)
        cv2.rectangle(image, (187, 75), (233, 100), accent, -1)
        cv2.rectangle(image, (158, 164), (262, 177), accent, -1)
        cv2.rectangle(image, (158, 210), (262, 223), accent, -1)
    elif kind == "lunchbox":
        cv2.rectangle(image, (92, 142), (328, 292), color, -1)
        cv2.ellipse(image, (210, 142), (118, 26), 0, 180, 360, color, -1)
        cv2.rectangle(image, (114, 112), (306, 154), accent, -1)
        cv2.rectangle(image, (164, 98), (256, 120), accent, -1)
    elif kind == "sock":
        cv2.rectangle(image, (159, 92), (262, 257), color, -1)
        cv2.rectangle(image, (159, 209), (284, 266), color, -1)
        for y in (128, 165, 202):
            cv2.line(image, (160, y), (261, y), accent, 10)
    elif kind == "hat":
        cv2.ellipse(image, (210, 227), (150, 48), 0, 0, 360, accent, -1)
        cv2.ellipse(image, (210, 195), (98, 102), 180, 0, 360, color, -1)
        cv2.rectangle(image, (174, 90), (246, 150), color, -1)
        cv2.ellipse(image, (210, 150), (36, 34), 0, 180, 360, color, -1)
    elif kind == "toy":
        cv2.rectangle(image, (96, 162), (324, 270), color, -1)
        cv2.rectangle(image, (150, 112), (275, 174), accent, -1)
        cv2.rectangle(image, (168, 126), (212, 158), (220, 235, 245), -1)
        cv2.rectangle(image, (220, 126), (258, 158), (220, 235, 245), -1)
        for x in (145, 278):
            cv2.circle(image, (x, 270), 29, (52, 56, 61), -1)
            cv2.circle(image, (x, 270), 12, (211, 204, 190), -1)
    elif kind == "shoe":
        cv2.ellipse(image, (205, 244), (128, 65), 0, 0, 360, color, -1)
        cv2.rectangle(image, (196, 170), (290, 245), color, -1)
        cv2.ellipse(image, (203, 276), (130, 20), 0, 0, 360, accent, -1)
        for x in (205, 234, 263):
            cv2.line(image, (x, 184), (x + 18, 199), accent, 5)
    else:
        cv2.circle(image, (210, 210), 90, color, -1)

    cv2.GaussianBlur(shadow, (0, 0), 20, dst=shadow)
    image = cv2.addWeighted(image, 1.0, shadow, 0.11, 0)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise RuntimeError("Could not create demo image")
    return encoded.tobytes()
