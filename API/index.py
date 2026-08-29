from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import uvicorn
from datetime import datetime
import os

from .models import CheckRequest
from .engine import engine
from .pools import pool_manager
from .config import settings

app = FastAPI(
    title="SHOPI API",
    description="Self-hosted Shopify payment checker",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create data directory
os.makedirs(settings.DATA_DIR, exist_ok=True)

@app.get("/")
async def check_card(
    card: str = Query(..., description="Card: CC|MM|YY|CVV"),
    proxy: Optional[str] = Query(None, description="Optional proxy"),
    email: Optional[str] = Query(None, description="Optional email"),
    site: Optional[str] = Query(None, description="Optional site URL")
):
    """Check a single card"""
    result, error = engine.process_checkout(card, proxy, email, site)
    if not result:
        raise HTTPException(status_code=500, detail=error)
    return result

@app.post("/bulk")
async def bulk_check(request: List[CheckRequest]):
    """Check multiple cards"""
    results = []
    for req in request:
        result, error = engine.process_checkout(
            req.card, req.proxy, req.email, req.site
        )
        results.append({
            "success": result is not None,
            "card": req.card,
            "result": result,
            "error": error
        })
    
    return {
        "total": len(results),
        "successful": len([r for r in results if r["success"]]),
        "results": results
    }

@app.get("/stats")
async def get_stats():
    """Get current statistics"""
    return {
        "sites": len(pool_manager.sites),
        "proxies": len(pool_manager.proxies),
        "failed_sites": list(pool_manager.failed_sites),
        "failed_proxies": list(pool_manager.failed_proxies),
        "engine_stats": engine.stats,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/refresh")
async def refresh_pools():
    """Refresh sites and proxies from files"""
    pool_manager.refresh()
    return {"status": "refreshed"}

@app.get("/health")
async def health_check():
    """Health check endpoint for Render"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "shopi-api",
        "version": "1.0.0"
    }

@app.on_event("startup")
async def startup_event():
    print(f"[+] SHOPI API starting")
    print(f"[+] Data directory: {settings.DATA_DIR}")
    print(f"[+] Sites loaded: {len(pool_manager.sites)}")
    print(f"[+] Proxies loaded: {len(pool_manager.proxies)}")

if __name__ == "__main__":
    uvicorn.run(
        "api.index:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.PARALLEL_WORKERS
)
