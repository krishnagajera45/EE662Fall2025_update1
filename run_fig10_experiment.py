#!/usr/bin/env python3
"""
Run Figure 10 experiment: Fraction of connected nodes over time for different traffic loads.

This script runs simulations with varying traffic loads to show how network 
connectivity degrades faster under higher traffic due to increased energy consumption.
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime

CONFIG_FILE = "wsnlab/source/config.py"
SIMULATION_SCRIPT = "wsnlab/data_collection_tree.py"

def update_config(data_packet_interval, baseline_current, battery_energy, sim_duration):
    """Update config file with experiment parameters."""
    with open(CONFIG_FILE, 'r') as f:
        lines = f.readlines()
    
    with open(CONFIG_FILE, 'w') as f:
        for line in lines:
            if line.strip().startswith('DATA_PACKET_INTERVAL ='):
                f.write(f'DATA_PACKET_INTERVAL = {data_packet_interval}  # Fig 10: Traffic load\n')
            elif line.strip().startswith('BASELINE_CURRENT ='):
                f.write(f'BASELINE_CURRENT = {baseline_current}  # Fig 10: Moderate baseline\n')
            elif line.strip().startswith('BATTERY_ENERGY_TOTAL ='):
                f.write(f'BATTERY_ENERGY_TOTAL = {battery_energy}  # Fig 10: Moderate energy\n')
            elif line.strip().startswith('SIM_DURATION ='):
                f.write(f'SIM_DURATION = {sim_duration}  # Fig 10: Track connectivity over time\n')
            elif line.strip().startswith('SIM_VISUALIZATION ='):
                f.write('SIM_VISUALIZATION = False  # Disable for faster simulation\n')
            else:
                f.write(line)

def main():
    """Main function."""
    print("="*70)
    print("FIG. 10 EXPERIMENT: FRACTION OF CONNECTED NODES VS TIME")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Experiment parameters
    traffic_configs = [
        {'name': 'Very_Low_Traffic', 'interval': 10.0,  'label': 'Low traffic (10s)'},
        {'name': 'Low_Traffic',      'interval': 5.0,   'label': 'Medium traffic (5s)'},
        {'name': 'Medium_Traffic',   'interval': 2.0,   'label': 'High traffic (2s)'},
        {'name': 'High_Traffic',     'interval': 1.0,   'label': 'Very High traffic (1s)'},
    ]
    
    # Fixed parameters for all runs
    baseline_current = 0.001  # 1 mA (higher for energy depletion)
    battery_energy = 5.0  # 5 J (lower so nodes die within sim)
    sim_duration = 3000  # 3000s to see connectivity degradation
    
    print("\nExperiment design:")
    print(f"  - Battery energy: {battery_energy} J")
    print(f"  - Baseline current: {baseline_current} A ({baseline_current*1000} mA)")
    print(f"  - Simulation duration: {sim_duration} s")
    print(f"  - Traffic loads: {len(traffic_configs)} configurations")
    for cfg in traffic_configs:
        print(f"      • {cfg['label']}")
    print("\nThis will show how higher traffic loads cause faster connectivity degradation.")
    print("="*70)
    
    # Check if running in interactive mode
    if sys.stdin.isatty():
        response = input("\nContinue? (y/n): ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return
    else:
        print("\nAuto-starting (non-interactive mode)...")
    
    total_runs = len(traffic_configs)
    
    for i, traffic_cfg in enumerate(traffic_configs, 1):
        print(f"\n{'='*70}")
        print(f"RUN {i}/{total_runs}: {traffic_cfg['label']}")
        print(f"{'='*70}")
        
        # Update config
        update_config(
            data_packet_interval=traffic_cfg['interval'],
            baseline_current=baseline_current,
            battery_energy=battery_energy,
            sim_duration=sim_duration
        )
        
        print(f"  Configuration updated:")
        print(f"    DATA_PACKET_INTERVAL = {traffic_cfg['interval']} s")
        
        # Run simulation
        print(f"\n  Running simulation...")
        try:
            # Change to wsnlab directory to fix import issues
            original_dir = os.getcwd()
            os.chdir('wsnlab')
            
            result = subprocess.run(
                [sys.executable, 'data_collection_tree.py'],
                capture_output=True,
                text=True,
                timeout=7200,  # 2 hour timeout
                env={**os.environ, 'PYTHONUNBUFFERED': '1'}
            )
            
            os.chdir(original_dir)
            
            if result.returncode != 0:
                print(f"  ❌ Simulation failed!")
                if result.stderr:
                    print(f"  Error: {result.stderr[:500]}")
                continue
            
            print(f"  ✓ Simulation completed")
            
            # Check for results folder
            results_pattern = f"results_*_TI{traffic_cfg['interval']}s"
            matching_folders = list(Path('.').glob(results_pattern))
            
            if matching_folders:
                print(f"  ✓ Results saved: {matching_folders[0].name}")
            else:
                print(f"  ⚠️  Results folder not found (pattern: {results_pattern})")
                
        except subprocess.TimeoutExpired:
            print(f"  ❌ Simulation timed out!")
            continue
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    print(f"\n{'='*70}")
    print("ALL SIMULATIONS COMPLETE")
    print(f"{'='*70}")
    print(f"\nCompleted {total_runs} simulation runs")
    print("\nNext step: Generate Fig. 10 plot")
    print("  Run: python3 generate_all_plots.py --fig10")
    print("="*70)

if __name__ == "__main__":
    main()
