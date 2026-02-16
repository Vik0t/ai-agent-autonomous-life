from fastapi import FastAPI
import uvicorn

# Create the main app
app = FastAPI(title="Cyber Hackathon - Virtual World Simulator")

@app.get("/")
def read_root():
    return {"message": "Cyber Hackathon - Virtual World Simulator"}

if __name__ == "__main__":
    # Run the API server directly
    import sys
    import os
    # Add the current directory to the path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # Import and run the API app
    from api import app as api_app
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)