from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.optimizer import OptimizationRequest, run_hrp_optimization

app = FastAPI(title="AI Portfolio Optimizer 2025")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "HRP Optimizer API is running"}

@app.post("/api/optimize")
def optimize(payload: OptimizationRequest):
    result = run_hrp_optimization(payload.tickers)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result
