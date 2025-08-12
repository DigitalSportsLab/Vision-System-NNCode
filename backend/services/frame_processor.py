import cv2, numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from backend.monitoring.metrics import metrics

DETECTION_COLORS = {"person": (0,0,255), "bottle": (0,255,0), "potted plant": (255,0,0)}
KEYPOINT_COLOR = (0,255,0); SKELETON_COLOR = (0,255,255)

# pro Kamera: letzter Zeitpunkt je Klasse (10s Cooldown)
detection_times = defaultdict(lambda: defaultdict(lambda: datetime.min))

def process_frame(frame, result, camera_id: int, model_task: str):
    with metrics.measure_latency(str(camera_id), model_task):
        annotated = frame.copy()

        # Pose
        if getattr(result, "keypoints", None) is not None:
            for person in result.keypoints:
                kps = person.data[0].cpu().numpy()
                for x,y,c in kps:
                    if c > .5: cv2.circle(annotated, (int(x),int(y)), 4, KEYPOINT_COLOR, -1)
                for a,b in [[16,14],[14,12],[17,15],[15,13],[12,13],[6,12],[7,13],[6,7],[6,8],[7,9],[8,10],[9,11],[2,3],[1,2],[1,3],[2,4],[3,5],[4,6],[5,7]]:
                    if kps[a-1][2]>.5 and kps[b-1][2]>.5:
                        cv2.line(annotated,(int(kps[a-1][0]),int(kps[a-1][1])),(int(kps[b-1][0]),int(kps[b-1][1])),SKELETON_COLOR,2)

        # Segmentation
        if getattr(result, "masks", None) is not None:
            for i, mask in enumerate(result.masks):
                try:
                    class_id = int(result.boxes[i].cls[0])
                    class_name = result.names[class_id]
                    if class_name in DETECTION_COLORS:
                        m = mask.data.cpu().numpy()[0]
                        if m.shape[:2] != frame.shape[:2]:
                            m = cv2.resize(m, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_NEAREST)
                        binm = (m > .5).astype(np.uint8)
                        overlay = np.zeros_like(frame)
                        overlay[binm==1] = DETECTION_COLORS[class_name]
                        area = binm > 0
                        annotated[area] = cv2.addWeighted(annotated[area], 0.6, overlay[area], 0.4, 0)
                except Exception:
                    continue

        # Detection + Metriken + Cooldown
        if getattr(result, "boxes", None) is not None:
            for box in result.boxes:
                x1,y1,x2,y2 = box.xyxy[0].cpu().numpy()
                cls_id = int(box.cls[0]); conf = float(box.conf[0])
                class_name = result.names[cls_id]

                # zeichnen für alle bekannten Klassen, sonst Standardfarbe
                color = DETECTION_COLORS.get(class_name, (200,200,200))
                cv2.rectangle(annotated,(int(x1),int(y1)),(int(x2),int(y2)),color,2)
                label = f"{class_name} {conf:.2f}"
                cv2.putText(annotated,label,(int(x1), max(int(y1)-6, 12)),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,255,255),2)

                valid = (class_name=="person") or (class_name=="bottle" and model_task=="detect")
                if valid:
                    # Metriken pro Box (Bugfix gegenüber Original)
                    metrics.record_detection(str(camera_id), class_name, model_task, conf)

                    now = datetime.now()
                    last = detection_times[camera_id][class_name]
                    if last == datetime.min:
                        detection_times[camera_id][class_name] = now
                    elif now - last >= timedelta(seconds=10):
                        yield {"class_name": class_name}
                        detection_times[camera_id][class_name] = datetime.min

        cv2.putText(annotated, f"{frame.shape[1]}x{frame.shape[0]}", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
        yield {"frame": annotated}
