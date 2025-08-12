import cv2
from time import perf_counter

from backend.services.frame_processor import process_frame
from backend.services.detection_service import save_event
from backend.services.video_manager import (
    set_latest, set_progress, set_error, video_running
)
from backend.db_settings import SessionLocal
from backend.monitoring.metrics import metrics


def run_video_job(job_id: str, file_path: str, model, model_task: str, camera_id: int | None):
    """
    Liest ein Videofile wie einen Stream, verarbeitet Frames mit deinem process_frame
    und speichert Events. Metriken:
      - active_video_jobs: (DEKREMENT hier bei natürlichem Ende)
      - video_frames_processed_total{job_id}
      - video_frame_latency_seconds{job_id, model_type}
      - video_job_errors_total{job_id}
    """
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        set_error(job_id, "Could not open video")
        metrics.video_job_errors.labels(job_id=job_id).inc()
        video_running[job_id] = False
        return

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    idx = 0

    try:
        while video_running.get(job_id, False):
            ok, frame = cap.read()
            if not ok:
                break  # Video zu Ende

            t0 = perf_counter()
            try:
                # Inferenz
                results = model(frame)

                # Annotieren + Events sammeln
                events = []
                for out in process_frame(frame, results[0], camera_id or -1, model_task):
                    if "class_name" in out:
                        events.append(out["class_name"])
                    elif "frame" in out:
                        # Aktuelles annotiertes Frame bereitstellen
                        ok_jpg, buf = cv2.imencode(".jpg", out["frame"])
                        if ok_jpg:
                            set_latest(job_id, buf.tobytes())

                # Metriken für dieses Frame
                metrics.video_frames_processed.labels(job_id=job_id).inc()
                metrics.video_frame_latency.labels(
                    job_id=job_id, model_type=model_task
                ).observe(perf_counter() - t0)

                # Events persistieren (gleich wie Live)
                if events:
                    db = SessionLocal()
                    try:
                        persisted_model_type = "objectDetection" if model_task == "detect" else model_task
                        for cls in events:
                            save_event(db, cls, persisted_model_type, camera_id or -1)
                    finally:
                        db.close()

            except Exception as e:
                # Fehler im Frame-Handling
                set_error(job_id, str(e))
                metrics.video_job_errors.labels(job_id=job_id).inc()

            # Fortschritt (falls FrameCount bekannt)
            idx += 1
            if total > 0:
                set_progress(job_id, 100.0 * idx / total)

        # Ende erreicht → auf 100% setzen
        set_progress(job_id, 100.0)

    except Exception as e:
        # Unerwarteter Fehler außerhalb des Frame-Loops
        set_error(job_id, str(e))
        metrics.video_job_errors.labels(job_id=job_id).inc()

    finally:
        cap.release()
        video_running[job_id] = False
        metrics.active_video_jobs.dec()
