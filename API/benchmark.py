#!/usr/bin/env python3
import asyncio
import time
import json
import httpx
from datetime import datetime

BASE_URL = "http://localhost:4463"

ENDPOINTS = [
    "/f1/drivers_standings/",
    "/f1/constructors_standings/",
    "/f1/last_race/",
    "/f1/next_race/",
    "/f1/tyre_usage/",
]

async def benchmark():
    async with httpx.AsyncClient(timeout=30) as client:
        results = {}
        
        for endpoint in ENDPOINTS:
            print(f"\nTesting {endpoint}...")
            
            # Cold start (first call)
            start = time.time()
            try:
                r = await client.get(BASE_URL + endpoint)
                cold_time = time.time() - start
                cold_size = len(r.content)
                print(f"  Cold start: {cold_time:.3f}s, {cold_size} bytes")
            except Exception as e:
                print(f"  Cold start FAILED: {e}")
                continue
            
            # Warm (cached)
            times = []
            for i in range(5):
                start = time.time()
                r = await client.get(BASE_URL + endpoint)
                times.append(time.time() - start)
            
            avg_warm = sum(times) / len(times)
            print(f"  Warm (avg of 5): {avg_warm*1000:.1f}ms")
            
            results[endpoint] = {
                "cold_ms": cold_time * 1000,
                "warm_ms": avg_warm * 1000,
                "size_bytes": cold_size,
            }
        
        print("\n" + "="*60)
        print("BENCHMARK RESULTS")
        print("="*60)
        print(json.dumps(results, indent=2))
        
        return results

if __name__ == "__main__":
    asyncio.run(benchmark())
