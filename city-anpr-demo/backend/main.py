from fastapi import FastAPI

app = FastAPI(
    title="City ANPR Demo API",
    description="AI based traffic monitoring and ANPR prototype",
    version="1.0"
)


@app.get("/")
def home():
    return {
        "status": "running",
        "project": "City ANPR Demo",
        "message": "Backend is working"
    }


@app.get("/health")
def health():
    return {
        "ok": True
    }