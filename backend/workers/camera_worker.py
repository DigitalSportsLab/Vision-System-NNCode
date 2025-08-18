import time
import cv2
import threading
from typing import Union

from backend.services.frame_processor import process_frame
from backend.services.detection_service import save_event
from backend.services.camera_manager import (
    video_captures, camera_running, set_latest, cleanup, set_placeholder_frame
)
from backend.db_settings import SessionLocal
from backend.monitoring.metrics import metrics
from backend.services.camera_manager import set_placeholder_frame


def _is_url(src: Union[int, str]) -> bool:
    return isinstance(src, str) and src.startswith(("rtsp://", "http://", "https://"))


def run_camera_loop(camera_id: int, stream_src: Union[int, str], adapter, model_task: str, thread_name: str):
    """
    Liest einen Live-Stream (USB/RTSP/HTTP/Datei) und nutzt das generische Adapter-Interface.
    Erwartung an adapter:
      - adapter.predict(frame) -> obj mit .raw (Model-Roh-Output)
      - optional: adapter.task (Enum/String) wurde im Router via adapter.task.value als model_task übergeben
    process_frame(frame, raw, camera_id, model_task) soll Dicts yielden:
      - {"frame": annotated_frame}  -> wird als JPEG gepusht
      - {"class_name": "..."}       -> wird als Event persistiert
    """
    current = threading.current_thread()
    current.name = thread_name

    # Kamera-Status-Metrik setzen
    try:
        metrics.camera_status.labels(camera_id=str(camera_id), camera_name=thread_name).set(1)
    except Exception:
        pass

    cap = None
    try:
        # Quelle öffnen (FFMPEG für URLs stabiler)
        cap = cv2.VideoCapture(stream_src, cv2.CAP_FFMPEG) if _is_url(stream_src) else cv2.VideoCapture(stream_src)
        if not cap.isOpened():
            metrics.record_error(str(camera_id), "OpenCaptureError", "camera_worker_init")
            camera_running[camera_id] = False
            # Wir dekrementieren Metrics hier (Worker ist verantwortlich) und machen cleanup ohne weiteres dec()
            metrics.active_cameras.dec()
            cleanup(camera_id, dec_metric=False)
            return
        set_placeholder_frame(camera_id, text="Starting...")
        # erst NACH erfolgreichem Open registrieren
        video_captures[camera_id] = cap

        # Optional: sofort ein Platzhalter-Frame schreiben, damit /process_frame/{id} sofort 200 liefert
        try:
            set_placeholder_frame(camera_id, text="Starting...")
        except Exception:
            pass

        # (optional) Basis-Props – werden ignoriert, wenn nicht unterstützt
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
        except Exception:
            pass

        idle_backoff = 0.02  # 20ms, damit kein Busy-Loop entsteht

        while camera_running.get(camera_id, False):
            ok, frame = cap.read()
            if not ok:
                time.sleep(idle_backoff)
                continue

            try:
                pred = adapter.predict(frame)  # muss ein Objekt mit .raw liefern
            except Exception as e:
                metrics.record_error(str(camera_id), type(e).__name__, "adapter_predict")
                time.sleep(idle_backoff)
                continue

            # process_frame misst intern Latenz via metrics.measure_latency(...)
            events_to_persist = []
            try:
                for out in process_frame(frame, getattr(pred, "raw", pred), camera_id, model_task):
                    if "frame" in out:
                        ok_jpg, buf = cv2.imencode(".jpg", out["frame"])
                        if ok_jpg:
                            try:
                                set_latest(camera_id, buf.tobytes())
                            except Exception as e:
                                metrics.record_error(str(camera_id), type(e).__name__, "set_latest")
                    elif "class_name" in out:
                        events_to_persist.append(out["class_name"])
            except Exception as e:
                metrics.record_error(str(camera_id), type(e).__name__, "frame_processing")
                # Frame verwerfen, weiterlesen
                continue

            if events_to_persist:
                db = SessionLocal()
                try:
                    persisted_model_type = "objectDetection" if model_task == "detect" else model_task
                    for cls in events_to_persist:
                        try:
                            save_event(db, cls, persisted_model_type, camera_id)
                        except Exception as e:
                            metrics.record_error(str(camera_id), type(e).__name__, "save_event")
                    db.commit()
                except Exception:
                    db.rollback()
                finally:
                    db.close()

    finally:
        try:
            if cap is not None:
                cap.release()
        except Exception:
            pass
        # Worker ist für das Dec verantwortlich (der Router hat inc() gemacht)
        try:
            metrics.active_cameras.dec()
        except Exception:
            pass
        camera_running[camera_id] = False
        # cleanup entfernt Maps/Locks/Frames; dec_metric=False, weil wir hier schon dec() gemacht haben
        try:
            cleanup(camera_id, dec_metric=False)
        except Exception:
            pass
        try:
            metrics.camera_status.labels(camera_id=str(camera_id), camera_name=thread_name).set(0)
        except Exception:
            pass
