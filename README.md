# SHOPI API 🔥

Self-hosted Shopify payment checker.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Add your sites and proxies
nano data/sites.txt
nano data/proxies.txt

# Run locally
uvicorn api.index:app --host 0.0.0.0 --port 8081
