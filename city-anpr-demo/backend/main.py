from fastapi import FastAPI

from backend.anpr import process_plate


app = FastAPI(
    title="City ANPR Demo API",
    description="AI-powered city traffic intelligence presentation prototype",
    version="1.0.0",
)


@app.get("/")
def home():
    return {
        "status": "running",
        "project": "City ANPR Demo",
        "message": "Backend is working",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.get("/anpr-demo")
def anpr_demo():
    return process_plate()