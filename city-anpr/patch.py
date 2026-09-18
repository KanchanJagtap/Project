with open("backend/app/services/trajectory_service.py", "r") as f:
    content = f.read()
target = """                            previous_tracks = [t for t in vehicle.tracks if t.track_session_id != track.track_session_id]
                            if previous_tracks:
                                last_track = sorted(previous_tracks, key=lambda x: x.last_seen_at)[-1]
                            from_camera_id = last_track.camera_id
                            else:
                                from_camera_id = "UNKNOWN\""""
replacement = """                            previous_tracks = [t for t in vehicle.tracks if t.track_session_id != track.track_session_id]
                            if previous_tracks:
                                last_track = sorted(previous_tracks, key=lambda x: x.last_seen_at)[-1]
                                from_camera_id = last_track.camera_id
                            else:
                                from_camera_id = "UNKNOWN\""""
with open("backend/app/services/trajectory_service.py", "w") as f:
    f.write(content.replace(target, replacement))
