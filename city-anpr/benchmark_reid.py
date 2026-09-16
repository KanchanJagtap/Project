import cv2
import time
import numpy as np
import os
from ai.reid.onnx_encoder import ONNXAppearanceEncoder
from ai.reid.crop import extract_vehicle_crop

def run_benchmark():
    model_path = os.environ.get("REID_MODEL_PATH", "vehicle_vit_clip_reid.onnx")
    if not os.path.exists(model_path):
        print(f"Model not found: {model_path}")
        return
        
    print("Loading Real Encoder...")
    t0 = time.perf_counter()
    encoder = ONNXAppearanceEncoder(model_path)
    t1 = time.perf_counter()
    load_time = (t1 - t0) * 1000
    
    img = cv2.imread('data/test/indian-plates/images/image_0032.jpg')
    bbox = (278.256, 2.893, 2353.353, 1627.965)
    crop = extract_vehicle_crop(img, bbox)
    
    print("Warming up (5 runs)...")
    for _ in range(5):
        encoder.encode(crop)
        
    runs = 10
    times = []
    
    print(f"Benchmarking ({runs} runs)...")
    for _ in range(runs):
        ts = time.perf_counter()
        emb = encoder.encode(crop)
        times.append((time.perf_counter() - ts) * 1000)
        
    median_lat = np.median(times)
    
    print("\n=== BENCHMARK REPORT ===")
    print(f"Provider: {encoder.active_provider}")
    print(f"Model Load Time: {load_time:.2f} ms")
    print(f"Median Inference Latency: {median_lat:.2f} ms")
    print(f"Embedding Dimension: {emb.dimension}")
    print(f"Normalized Norm: {np.linalg.norm(emb.vector):.6f}")
    
    # Also get the similarity to the second crop for the report
    img2 = cv2.imread('data/test/indian-plates/images/image_0026.jpg')
    bbox2 = (52.137, 406.955, 1968.0, 2953.866)
    crop2 = extract_vehicle_crop(img2, bbox2)
    emb2 = encoder.encode(crop2)
    
    from ai.reid.similarity import cosine_similarity
    sim = cosine_similarity(emb, emb2)
    print(f"Similarity (0032 vs 0026): {sim:.4f}")
    print(f"Crop 1 size: {crop.shape}")
    print(f"Crop 2 size: {crop2.shape}")

if __name__ == '__main__':
    run_benchmark()
