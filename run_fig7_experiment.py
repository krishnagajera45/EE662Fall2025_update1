#!/usr/bin/env python3
"""
Figure 7 Experiment: Average Remaining Energy Over Time
CT+Mesh vs CT-only comparison

Runs two simulations:
1. CT-only (ENABLE_MULTIHOP_DISCOVERY = False)
2. CT+Mesh (ENABLE_MULTIHOP_DISCOVERY = True)

Tracks average remaining energy over time (0-1000s) to match reference figure.
"""

import subprocess
import os
import time
import json
from pathlib import Path
import re
import shutil

BASE_DIR = Path(__file__).parent.absolute()
WSNLAB_DIR = BASE_DIR / "wsnlab"
CONFIG_FILE = WSNLAB_DIR / "source" / "config.py"
SIMULATION_SCRIPT = WSNLAB_DIR / "data_collection_tree.py"

def update_config(multihop_enabled, energy_budget=2.0, sim_duration=5000):
    """
    Update config.py for Fig 7 experiment.
    
    Args:
        multihop_enabled: True for CT+Mesh, False for CT-only
        energy_budget: Initial energy per node (Joules) - use ~2J to match reference
        sim_duration: Simulation duration in seconds (5000s for extended run)
    """
    strategy = "CT+Mesh" if multihop_enabled else "CT-only"
    print(f"\n📝 Updating config for {strategy}:")
    print(f"   - Multihop discovery: {multihop_enabled}")
    print(f"   - Energy budget: {energy_budget}J")
    print(f"   - Duration: {sim_duration}s")
    
    with open(CONFIG_FILE, 'r') as f:
        config_content = f.read()
    
    # Update multihop discovery
    config_content = re.sub(
        r'ENABLE_MULTIHOP_DISCOVERY = (True|False).*',
        f'ENABLE_MULTIHOP_DISCOVERY = {multihop_enabled}  # Fig 7: {strategy}',
        config_content
    )
    
    # Update simulation duration
    config_content = re.sub(
        r'SIM_DURATION = \d+.*',
        f'SIM_DURATION = {sim_duration}  # Fig 7: Energy depletion comparison',
        config_content
    )
    
    # Update energy budget
    config_content = re.sub(
        r'BATTERY_ENERGY_TOTAL = [\d.]+.*',
        f'BATTERY_ENERGY_TOTAL = {energy_budget}  # Fig 7: Match reference (~2J)',
        config_content
    )
    
    # Update baseline current (use realistic value for energy depletion)
    config_content = re.sub(
        r'BASELINE_CURRENT = [\d.]+.*',
        f'BASELINE_CURRENT = 0.0015  # Fig 7: ~1.5mA for realistic depletion',
        config_content
    )
    
    # Update traffic interval (moderate traffic)
    config_content = re.sub(
        r'DATA_PACKET_INTERVAL = [\d.]+.*',
        f'DATA_PACKET_INTERVAL = 10  # Fig 7: Moderate traffic',
        config_content
    )
    
    # Disable visualization for speed
    config_content = re.sub(
        r'SIM_VISUALIZATION = (True|False).*',
        'SIM_VISUALIZATION = False  # Fig 7: Faster simulation',
        config_content
    )
    
    # No packet loss
    config_content = re.sub(
        r'PACKET_LOSS_RATE = [\d.]+.*',
        'PACKET_LOSS_RATE = 0  # Fig 7: No artificial loss',
        config_content
    )
    
    with open(CONFIG_FILE, 'w') as f:
        f.write(config_content)
    
    print("   ✓ Config updated")

def run_simulation(strategy_name, multihop_enabled):
    """
    Run a single simulation and save results.
    
    Returns:
        success: True if simulation completed successfully
    """
    print(f"\n{'='*70}")
    print(f"🚀 Starting simulation: {strategy_name}")
    print(f"{'='*70}\n")
    
    # Update configuration
    update_config(multihop_enabled, energy_budget=2.0, sim_duration=5000)
    
    start_time = time.time()
    
    try:
        # Run simulation
        result = subprocess.run(
            ['python3', 'data_collection_tree.py'],
            cwd=str(WSNLAB_DIR),
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        elapsed_time = time.time() - start_time
        
        if result.returncode == 0:
            print(f"\n✅ Simulation completed in {elapsed_time/60:.1f} minutes")
            
            # Save results
            results_folder = BASE_DIR / f"results_fig7_{strategy_name.lower().replace('+', '_')}"
            
            # Remove old results if they exist
            if results_folder.exists():
                shutil.rmtree(results_folder)
            
            results_folder.mkdir(parents=True, exist_ok=True)
            
            # Copy result files
            files_to_copy = [
                'connectivity_over_time.csv',
                'cluster_members.csv',
                'averagePower_by_time.csv',
                'totalPower_by_time.csv',
                'energy_by_node.csv',
                'nodePower_over_time.csv'
            ]
            
            import glob
            for pattern in files_to_copy:
                file_path = WSNLAB_DIR / pattern
                if file_path.exists():
                    shutil.copy2(file_path, results_folder / pattern)
            
            # Copy log files
            for log_file in glob.glob(str(WSNLAB_DIR / "wsn_log*.log")):
                shutil.copy2(log_file, results_folder / Path(log_file).name)
            
            # Create metadata
            metadata = {
                'strategy': strategy_name,
                'multihop_enabled': multihop_enabled,
                'energy_budget': 2.0,
                'sim_duration': 5000,
                'baseline_current': 0.0015,
                'data_packet_interval': 10,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'elapsed_time_minutes': elapsed_time / 60
            }
            
            with open(results_folder / 'simulation_metadata.json', 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"   📁 Results saved to: {results_folder.name}")
            return True
            
        else:
            print(f"\n❌ Simulation failed with return code {result.returncode}")
            print(f"Error output: {result.stderr[:500]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"\n⏱️  Simulation timed out after 1 hour")
        return False
    except Exception as e:
        print(f"\n❌ Error running simulation: {e}")
        return False

def main():
    """
    Main experiment runner for Figure 7.
    """
    print("\n" + "="*70)
    print("Figure 7 Experiment: Average Remaining Energy Over Time")
    print("CT+Mesh vs CT-only Comparison")
    print("="*70)
    print("\nThis experiment will:")
    print("  1. Run CT-only simulation (multihop disabled)")
    print("  2. Run CT+Mesh simulation (multihop enabled)")
    print("  3. Track average remaining energy over 5000 seconds")
    print("  4. Generate comparison plot")
    print(f"\nEstimated time: 60-90 minutes (2 simulations × 5000s)")
    print("="*70)
    
    start_time_total = time.time()
    
    # Run CT-only simulation
    success1 = run_simulation("CT-only", multihop_enabled=False)
    
    if success1:
        print(f"\n⏸️  Pausing 5 seconds before next simulation...")
        time.sleep(5)
    
    # Run CT+Mesh simulation
    success2 = run_simulation("CT+Mesh", multihop_enabled=True)
    
    # Summary
    elapsed_total = time.time() - start_time_total
    
    print(f"\n\n{'='*70}")
    print(f"✅ EXPERIMENTS COMPLETED!")
    print(f"{'='*70}")
    print(f"\nTotal time: {elapsed_total/60:.1f} minutes")
    print(f"\nResults:")
    print(f"  {'✓' if success1 else '✗'} CT-only simulation")
    print(f"  {'✓' if success2 else '✗'} CT+Mesh simulation")
    
    print(f"\n{'='*70}")
    print(f"Now generating plot...")
    print(f"{'='*70}\n")
    
    # Generate plot
    try:
        subprocess.run(
            ['python3', str(BASE_DIR / 'generate_all_plots.py'), '--fig7'],
            check=True
        )
        print("\n✅ Plot generated successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\n⚠️  Error generating plot: {e}")
    
    print(f"\n{'='*70}")
    print(f"Figure 7 experiment complete!")
    print(f"Check 'results_fig7_*' folders for detailed results")
    print(f"Check 'fig7_avg_energy_ct_comparison.png' for the plot")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
