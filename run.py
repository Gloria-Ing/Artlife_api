import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    print(f"Starting Artlife FastAPI server at http://{HOST}:{PORT}")
    print(f"Interactive Swagger Documentation available at http://localhost:{PORT}/docs")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
