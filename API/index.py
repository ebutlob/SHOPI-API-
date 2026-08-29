from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Optional, List
import uvicorn
from datetime import datetime
import os
import io
import tempfile
import shutil

from .models import CheckRequest
from .engine import engine
from .pools import pool_manager
from .config import settings
from .auto_discover import discoverer

app = FastAPI(
    title="SHOPI API",
    description="Self-hosted Shopify payment checker with auto-discovery",
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

@app.post("/discover/upload")
async def discover_from_file(
    file: UploadFile = File(...),
    output: Optional[str] = "data/sites_auto.txt"
):
    """Upload a text file with URLs and auto-discover products"""
    try:
        # Read uploaded file
        content = await file.read()
        lines = content.decode('utf-8').split('\n')
        
        # Extract URLs
        urls = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append(line)
        
        if not urls:
            return JSONResponse({
                "error": "No valid URLs found in file",
                "total": 0
            }, status_code=400)
        
        # Discover products
        results = discoverer.process_site_list(urls)
        
        # Generate sites file
        sites_content = discoverer.generate_sites_file(results, output)
        
        return JSONResponse({
            "success": True,
            "total": results['total'],
            "successful": results['success'],
            "failed": results['failed'],
            "output_file": output,
            "sites": results['sites'],
            "sites_content": sites_content
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/discover/single")
async def discover_single(
    url: str = Form(...)
):
    """Discover product for a single URL"""
    result = discoverer.discover_product(url)
    if not result:
        return JSONResponse({
            "error": "Could not discover product",
            "url": url
        }, status_code=404)
    return result

@app.get("/discover/bulk")
async def discover_bulk(
    urls: str = Query(..., description="Comma-separated list of URLs")
):
    """Discover products for multiple URLs"""
    url_list = [u.strip() for u in urls.split(',') if u.strip()]
    results = discoverer.process_site_list(url_list)
    return results

@app.post("/discover/generate_sites")
async def generate_sites_file(
    urls: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    output: str = Form("data/sites_auto.txt")
):
    """Generate sites.txt from URLs (upload file or text input)"""
    url_list = []
    
    if file:
        content = await file.read()
        lines = content.decode('utf-8').split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                url_list.append(line)
    
    if urls:
        url_list.extend([u.strip() for u in urls.split(',') if u.strip()])
    
    if not url_list:
        raise HTTPException(status_code=400, detail="No URLs provided")
    
    results = discoverer.process_site_list(url_list)
    content = discoverer.generate_sites_file(results, output)
    
    return PlainTextResponse(content, media_type="text/plain")

@app.get("/discover/status")
async def discover_status():
    """Get discovery status and cache info"""
    return {
        "cached_sites": len(discoverer.discovered),
        "cache_file": discoverer.cache_file
    }

@app.post("/discover/refresh")
async def refresh_discovery(
    url: str = Form(...)
):
    """Force refresh discovery for a URL"""
    # Remove from cache
    if url in discoverer.discovered:
        del discoverer.discovered[url]
        discoverer._save_cache()
    
    result = discoverer.discover_product(url)
    return result

@app.get("/stats")
async def get_stats():
    """Get current statistics"""
    return {
        "sites": len(pool_manager.sites),
        "proxies": len(pool_manager.proxies),
        "failed_sites": list(pool_manager.failed_sites),
        "failed_proxies": list(pool_manager.failed_proxies),
        "engine_stats": engine.stats,
        "discovery_cache": len(discoverer.discovered),
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
    print(f"[+] Discovery cache: {len(discoverer.discovered)} sites")
    print(f"[+] Sites loaded: {len(pool_manager.sites)}")

if __name__ == "__main__":
    uvicorn.run(
        "api.index:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.PARALLEL_WORKERS
    )):
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
