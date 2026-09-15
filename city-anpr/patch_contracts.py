import re

with open('ai/contracts/models.py', 'r') as f:
    content = f.read()

# Add AppearanceEmbedding class
embedding_class = """
@dataclass
class AppearanceEmbedding:
    vector: List[float]
    model_name: str
    dimension: int
    quality_score: Optional[float] = None

    def __post_init__(self) -> None:
        if self.dimension <= 0:
            raise ValueError("dimension must be positive")
        if len(self.vector) != self.dimension:
            raise ValueError(f"vector length {len(self.vector)} must match dimension {self.dimension}")
"""

# Insert AppearanceEmbedding before TrackedVehicle
content = content.replace("@dataclass\nclass TrackedVehicle:", embedding_class + "\n@dataclass\nclass TrackedVehicle:")

# Add embedding fields to TrackedVehicle
track_old = """    type_history: List[VehicleType] = field(default_factory=list)"""
track_new = """    type_history: List[VehicleType] = field(default_factory=list)
    appearance_embedding: Optional[AppearanceEmbedding] = None"""

content = content.replace(track_old, track_new)

with open('ai/contracts/models.py', 'w') as f:
    f.write(content)
print("Contracts patched.")
