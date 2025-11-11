from fastapi import FastAPI

app = FastAPI(title="Relume API", version="0.1.0")

@app.get("/")
def root():
    return {"message": "Relume API online"}

@app.get("/health")
def health():
    return {"status": "ok", "app": "relume-api"}
