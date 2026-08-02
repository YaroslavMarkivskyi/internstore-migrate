import uuid

from security.config import Settings


def build_video_url(settings: Settings, visit_log_id: uuid.UUID) -> str:
    """mock-camera serves the same fixed .mp4 on any GET, so this URL only
    needs to be unique per visit_log row, not resolvable to a distinct
    file — a real ESP32-CAM URL replaces camera_base_url in prod."""
    return f"{settings.camera_base_url}/video/{visit_log_id}.mp4"
