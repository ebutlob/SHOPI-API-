#!/usr/bin/env python3
import random

def rotate_proxies():
    with open("data/proxies.txt", 'r') as f:
        proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    random.shuffle(proxies)
    
    with open("data/proxies.txt", 'w') as f:
        f.write("# Format: host:port:username:password\n")
        for proxy in proxies:
            f.write(f"{proxy}\n")
    
    print("✅ Proxies shuffled")

if __name__ == "__main__":
    rotate_proxies()
