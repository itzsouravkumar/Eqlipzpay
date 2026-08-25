from fastapi import FastAPI

app = FastAPI(title="EqlipZ Pay API")

@app.get("/")
def read_root():
    return {"status": "operational", "service": "EqlipZ Pay"}
