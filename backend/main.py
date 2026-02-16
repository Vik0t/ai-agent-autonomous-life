from fastapi import FastAPI
import uvicorn
from . import api

# Create the main app
app = FastAPI(title="Cyber Hackathon - Virtual World Simulator")

# Include the API routes
app.include_router(api.app)

@app.get("/")
def read_root():
    return {"message": "Cyber Hackathon - Virtual World Simulator"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)