#!/usr/bin/env python3
import requests
import sys

def check_health():
    try:
        response = requests.get("http://localhost:8081/health", timeout=5)
        if response.status_code == 200:
            print("✅ SHOPI API is healthy")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Running health check...")
    sys.exit(0 if check_health() else 1)
