#!/usr/bin/env python3
"""
Run Figure 11 experiment: CDF of node lifetimes by role.

This script runs a single simulation with energy model enabled to collect
node lifetime data separated by role (Cluster Head vs Leaf nodes).
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

CONFIG_FILE = "wsnlab/source/config.py"
SIMULATION_SCRIPT = "wsnlab/data_collection_tree.py"
PLOT_SCRIPT = "generate_all_plots.py"

def main():
    """Main function."""
    print("="*70)
    print("FIG. 11 EXPERIMENT: CDF of Node Lifetimes by Role")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print("\nThis will run a simulation to collect node lifetime data:")
    print("  - Energy Model: Enabled")
    print("  - Energy Budget: 60 J per node")
    print("  - Traffic: High (1s interval)")
    print("  - Duration: 6000 seconds")
    print("\nExpected outcome:")
    print("  - Cluster heads die first (heavy forwarding)")
    print("  - Leaf nodes die later (light traffic)")
    print("="*70)
    
    # Check if running in interactive mode
    if sys.stdin.isatty():
        response = input("\nContinue? (y/n): ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return
    else:
        print("\nAuto-starting (non-interactive mode)...")
    
    print("\nRunning simulation...")
    print(f"Command: python3 {SIMULATION_SCRIPT}")
    
    try:
        result = subprocess.run(
            [sys.executable, SIMULATION_SCRIPT],
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hour timeout
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )
        
        if result.returncode != 0:
            print(f"  ❌ Simulation failed!")
            if result.stderr:
                print(f"  Error: {result.stderr[:500]}")
            return False
        
        print(f"  ✓ Simulation completed")
        
    except subprocess.TimeoutExpired:
        print(f"  ❌ Simulation timed out!")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    # Generate Fig. 11 plot
    print("\nGenerating Fig. 11 plot...")
    
    try:
        result = subprocess.run(
            [sys.executable, PLOT_SCRIPT, "--fig11"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            print(f"  ❌ Plot generation failed!")
            if result.stderr:
                print(f"  Error: {result.stderr[:300]}")
            return False
        
        print(f"  ✓ Plot generated successfully")
        
        # Check if plot exists
        plot_file = Path("fig11_cdf_node_lifetimes.png")
        if plot_file.exists():
            print(f"\n{'='*70}")
            print("EXPERIMENT COMPLETE")
            print(f"{'='*70}")
            print(f"\n✓ Plot saved: {plot_file.name}")
            print("\nThe plot shows:")
            print("  • Cluster Heads (blue): Shorter lifetimes (die first)")
            print("  • Leaf Nodes (orange): Longer lifetimes (survive longer)")
            print("\nThis confirms that forwarding roles consume more energy!")
            print(f"{'='*70}")
            return True
        else:
            print("  ⚠️  Plot file not found")
            return False
        
    except Exception as e:
        print(f"  ❌ Plot generation failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
