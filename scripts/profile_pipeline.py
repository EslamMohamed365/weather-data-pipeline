"""
Profile the ETL pipeline to identify bottlenecks.

Usage:
    python scripts/profile_pipeline.py

Output:
    - pipeline.prof (cProfile output)
    - pipeline_profile.txt (human-readable)
"""

import cProfile
import pstats
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline import run_pipeline


def profile_pipeline():
    """Run pipeline with cProfile."""
    profiler = cProfile.Profile()

    print("Starting profiling...")
    profiler.enable()

    # Run pipeline
    stats = run_pipeline()

    profiler.disable()
    print("\nProfiling complete!")

    # Save binary profile
    profiler.dump_stats("pipeline.prof")
    print("Binary profile saved to: pipeline.prof")

    # Generate human-readable report
    with open("pipeline_profile.txt", "w") as f:
        ps = pstats.Stats(profiler, stream=f)
        ps.strip_dirs()
        ps.sort_stats("cumulative")
        ps.print_stats(50)  # Top 50 functions

    print("Human-readable profile saved to: pipeline_profile.txt")

    # Print summary to console
    ps = pstats.Stats(profiler)
    ps.strip_dirs()
    ps.sort_stats("cumulative")
    print("\n" + "=" * 80)
    print("TOP 10 SLOWEST FUNCTIONS (by cumulative time)")
    print("=" * 80)
    ps.print_stats(10)

    return stats


if __name__ == "__main__":
    profile_pipeline()
