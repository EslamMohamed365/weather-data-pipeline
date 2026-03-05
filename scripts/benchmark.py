"""
Benchmark pipeline performance with different configurations.

Usage:
    python scripts/benchmark.py
"""

import time
import sys
from pathlib import Path
from statistics import mean, stdev

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extract import DEFAULT_CITIES
from pipeline import run_pipeline


def benchmark_pipeline(num_runs: int = 3):
    """
    Run pipeline multiple times and collect statistics.

    Args:
        num_runs: Number of benchmark runs (default: 3)
    """
    print("=" * 80)
    print(f"PIPELINE BENCHMARK - {num_runs} runs")
    print("=" * 80)

    durations = []

    for i in range(1, num_runs + 1):
        print(f"\n--- Run {i}/{num_runs} ---")
        start = time.time()

        stats = run_pipeline()

        duration = time.time() - start
        durations.append(duration)

        print(f"\nRun {i} completed in {duration:.2f}s")
        print(
            f"  Cities processed: {stats['cities_extracted']}/{stats['cities_requested']}"
        )
        print(f"  Rows inserted: {stats['rows_inserted']}")
        print(f"  Success: {stats['success']}")

    # Calculate statistics
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)
    print(f"Average duration: {mean(durations):.2f}s")
    print(f"Std deviation: {stdev(durations):.2f}s" if len(durations) > 1 else "N/A")
    print(f"Min duration: {min(durations):.2f}s")
    print(f"Max duration: {max(durations):.2f}s")
    print(f"Total time: {sum(durations):.2f}s")

    # Calculate throughput
    avg_duration = mean(durations)
    cities_per_sec = len(DEFAULT_CITIES) / avg_duration

    print("\n" + "-" * 80)
    print("THROUGHPUT")
    print("-" * 80)
    print(f"Cities per second: {cities_per_sec:.2f}")
    print(f"Rows per second: {840 / avg_duration:.2f}")

    # Projections
    print("\n" + "-" * 80)
    print("SCALABILITY PROJECTIONS")
    print("-" * 80)
    print(f"10 cities estimated: {avg_duration * 2:.1f}s")
    print(f"50 cities estimated: {avg_duration * 10:.1f}s")
    print(f"100 cities estimated: {avg_duration * 20:.1f}s")

    return {
        "avg_duration": mean(durations),
        "std_dev": stdev(durations) if len(durations) > 1 else 0,
        "min_duration": min(durations),
        "max_duration": max(durations),
        "cities_per_sec": cities_per_sec,
    }


if __name__ == "__main__":
    benchmark_pipeline(num_runs=3)
