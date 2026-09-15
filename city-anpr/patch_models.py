import re

with open('backend/app/models/tracking.py', 'r') as f:
    content = f.read()

# Add ARRAY_FLOAT_TYPE to imports
content = content.replace(
    "from backend.app.db.base import ARRAY_STR_TYPE, Base, JSON_TYPE, UUID_TYPE, utc_now",
    "from backend.app.db.base import ARRAY_FLOAT_TYPE, ARRAY_STR_TYPE, Base, JSON_TYPE, UUID_TYPE, utc_now"
)

# Add Re-ID fields to VehicleTrack
track_old = """    type_history: Mapped[List[str]] = mapped_column(
        ARRAY_STR_TYPE, default=list, nullable=False
    )"""

track_new = """    type_history: Mapped[List[str]] = mapped_column(
        ARRAY_STR_TYPE, default=list, nullable=False
    )
    appearance_embedding: Mapped[Optional[List[float]]] = mapped_column(
        ARRAY_FLOAT_TYPE, nullable=True
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    embedding_dimension: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    embedding_quality: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )"""

content = content.replace(track_old, track_new)

with open('backend/app/models/tracking.py', 'w') as f:
    f.write(content)
print("Models patched.")
