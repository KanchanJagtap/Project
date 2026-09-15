import re

with open('backend/app/adapters/ingestion.py', 'r') as f:
    content = f.read()

old_fields = """        trajectory_summary=[list(pt) for pt in track.trajectory],
        type_history=list(track.type_history),
    )"""
new_fields = """        trajectory_summary=[list(pt) for pt in track.trajectory],
        type_history=list(track.type_history),
        appearance_embedding=track.appearance_embedding.vector if track.appearance_embedding else None,
        embedding_model=track.appearance_embedding.model_name if track.appearance_embedding else None,
        embedding_dimension=track.appearance_embedding.dimension if track.appearance_embedding else None,
        embedding_quality=track.appearance_embedding.quality_score if track.appearance_embedding else None,
    )"""

content = content.replace(old_fields, new_fields)

with open('backend/app/adapters/ingestion.py', 'w') as f:
    f.write(content)
print("Ingestion adapter patched.")
