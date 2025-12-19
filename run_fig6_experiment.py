#!/usr/bin/env python3
"""
Multi-scenario experiment runner for Figure 6: Network Lifetime vs Energy Budget.

Runs simulations with varying initial energy budgets and traffic loads to measure
network lifetime (time until <80% nodes remain connected to sink).

Experiment Matrix:
- Energy budgets: [500, 1000, 1500, 2000, 2500] Joules (5 values)
- Traffic loads: low, medium, high (3 values)
- Total: 15 simulation runs

Each simulation runs for 5000s or until network lifetime is reached.
"""

import subprocess
import os
import time
import json
from pathlib import Path
import sys
import re

# Base directory
BASE_DIR = Path(__file__).parent.absolute()
WSNLAB_DIR = BASE_DIR / "wsnlab"
CONFIG_FILE = WSNLAB_DIR / "source" / "config.py"
SIMULATION_SCRIPT = WSNLAB_DIR / "data_collection_tree.py"

def update_config(energy_budget, traffic_interval, sim_duration=5000):
    """
    Update config.py with specific parameters for Fig 6.
    
    Args:
        energy_budget: Initial energy per node in Joules
        traffic_interval: Time between data packets (controls traffic load)
        sim_duration: Simulation duration in seconds
    """
    print(f"\n📝 Updating config.py:")
    print(f"   - Energy budget: {energy_budget}J")
    print(f"   - Traffic interval: {traffic_interval}s")
    print(f"   - Simulation duration: {sim_duration}s")
    
    with open(CONFIG_FILE, 'r') as f:
        config_content = f.read()
    
    # Update simulation duration
    config_content = re.sub(
        r'SIM_DURATION = \d+.*',
        f'SIM_DURATION = {sim_duration}  # Fig 6: Long enough to reach network lifetime',
        config_content
    )
    
    # Update visualization (off for faster simulation)
    config_content = re.sub(
        r'SIM_VISUALIZATION = (True|False).*',
        f'SIM_VISUALIZATION = False  # Fig 6: Faster simulation',
        config_content
    )
    
    # Update energy budget
    config_content = re.sub(
        r'BATTERY_ENERGY_TOTAL = [\d.]+.*',
        f'BATTERY_ENERGY_TOTAL = {energy_budget}  # Fig 6: Testing different energy budgets',
        config_content
    )
    
    # Update baseline current (keep moderate)
    config_content = re.sub(
        r'BASELINE_CURRENT = [\d.]+.*',
        f'BASELINE_CURRENT = 0.0003  # Fig 6: Moderate baseline',
        config_content
    )
    
    # Update traffic interval
    config_content = re.sub(
        r'DATA_PACKET_INTERVAL = [\d.]+.*',
        f'DATA_PACKET_INTERVAL = {traffic_interval}  # Fig 6: Traffic load control',
        config_content
    )
    
    # Update packet loss (none for baseline)
    config_content = re.sub(
        r'PACKET_LOSS_RATE = [\d.]+.*',
        f'PACKET_LOSS_RATE = 0  # Fig 6: No artificial packet loss',
        config_content
    )
    
    # Update node failures (none)
    config_content = re.sub(
        r'NUM_NODES_TO_FAIL = \d+.*',
        f'NUM_NODES_TO_FAIL = 0  # Fig 6: No node failures',
        config_content
    )
    
    with open(CONFIG_FILE, 'w') as f:
        f.write(config_content)
    
    print("   ✓ Config updated")


def run_simulation(scenario_name, energy_budget, traffic_name, traffic_interval):
    """
    Run a single simulation and save results.
    
    Returns:
        network_lifetime: Time in seconds when network lifetime was reached, or None
    """
    print(f"\n{'='*70}")
    print(f"🚀 Starting simulation: {scenario_name}")
    print(f"   Energy budget: {energy_budget}J")
    print(f"   Traffic: {traffic_name} (interval={traffic_interval}s)")
    print(f"{'='*70}\n")
    
    # Update configuration
    update_config(energy_budget, traffic_interval, sim_duration=5000)
    
    # Run simulation
    start_time = time.time()
    
    try:
        # Run simulation from wsnlab directory
        result = subprocess.run(
            ['python3', 'data_collection_tree.py'],
            cwd=str(WSNLAB_DIR),
            capture_output=True,
            text=True,
            timeout=7200  # 2 hour timeout
        )
        
        elapsed_time = time.time() - start_time
        
        if result.returncode == 0:
            print(f"\n✅ Simulation completed in {elapsed_time/60:.1f} minutes")
        
            # Parse network lifetime from output
            network_lifetime = None
            for line in result.stdout.split('\n'):
                if 'NETWORK LIFETIME REACHED' in line:
                    # Extract time from line like: "🔴 NETWORK LIFETIME REACHED at t=1234.56s"
                    match = re.search(r't=([\d.]+)s', line)
                    if match:
                        network_lifetime = float(match.group(1))
                        print(f"   📊 Network lifetime: {network_lifetime:.1f}s")
                        break
            
            if network_lifetime is None:
                print(f"   ⚠️  Network lifetime not reached within 5000s")
                network_lifetime = 5000.0  # Use full simulation time if not reached
            
            # Move and rename results
            results_folder = BASE_DIR / f"results_fig6_{scenario_name}"
            
            # Remove old results if they exist
            if results_folder.exists():
                import shutil
                shutil.rmtree(results_folder)
        
            # Move wsnlab directory contents to results folder
            wsnlab_results = WSNLAB_DIR
            results_folder.mkdir(parents=True, exist_ok=True)
            
            # Copy specific result files
            files_to_copy = [
            'connectivity_over_time.csv',
            'cluster_members.csv',
                'averagePower_by_time.csv',
                'totalPower_by_time.csv',
                'energy_by_node.csv',
                'wsn_log*.log'
            ]
            
            import shutil
            import glob
            for pattern in files_to_copy:
                for file in glob.glob(str(wsnlab_results / pattern)):
                    file_path = Path(file)
                    if file_path.exists():
                        shutil.copy2(file, results_folder / file_path.name)
        
            # Create metadata
            metadata = {
                'scenario_name': scenario_name,
                'energy_budget': energy_budget,
                'traffic_name': traffic_name,
                'traffic_interval': traffic_interval,
                'network_lifetime': network_lifetime,
                'sim_duration': 5000,
                'baseline_current': 0.0003,
                'packet_loss_rate': 0,
                'num_nodes': 100,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'elapsed_time_minutes': elapsed_time / 60
            }
            
            with open(results_folder / 'simulation_metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
            print(f"   📁 Results saved to: {results_folder.name}")
            
            return network_lifetime
            
        else:
            print(f"\n❌ Simulation failed with return code {result.returncode}")
            print(f"Error output: {result.stderr[:500]}")
            return None
        
    except subprocess.TimeoutExpired:
        print(f"\n⏱️  Simulation timed out after 2 hours")
        return None
    except Exception as e:
        print(f"\n❌ Error running simulation: {e}")
        return None


def main():
    """
    Main experiment runner for Figure 6.
    """
    print("\n" + "="*70)
    print("Figure 6 Experiment: Network Lifetime vs Energy Budget")
    print("="*70)
    print("\nThis experiment will:")
    print("  - Test 5 different energy budgets: [500, 1000, 1500, 2000, 2500] J")
    print("  - Test 3 traffic loads: low, medium, high")
    print("  - Total: 15 simulation runs")
    print("  - Each simulation runs up to 5000s")
    print(f"\nEstimated total time: 60-90 minutes")
    print("="*70)
    
    # Experiment matrix
    energy_budgets = [500, 1000, 1500, 2000, 2500]  # Joules
    
    # Traffic loads: (name, interval in seconds)
    # Lower interval = higher traffic load
    traffic_loads = [
        ('low', 20),      # Low traffic: packets every 20s
        ('medium', 10),   # Medium traffic: packets every 10s
        ('high', 5),      # High traffic: packets every 5s
    ]
    
    results_summary = []
    total_runs = len(energy_budgets) * len(traffic_loads)
    current_run = 0
    
    start_time_total = time.time()
    
    for energy in energy_budgets:
        for traffic_name, traffic_interval in traffic_loads:
            current_run += 1
            scenario_name = f"e{energy}_traffic{traffic_name}"
            
            print(f"\n\n{'#'*70}")
            print(f"# Run {current_run}/{total_runs}: {scenario_name}")
            print(f"{'#'*70}")
            
            network_lifetime = run_simulation(
                scenario_name=scenario_name,
                energy_budget=energy,
                traffic_name=traffic_name,
                traffic_interval=traffic_interval
            )
            
            results_summary.append({
                'scenario': scenario_name,
                'energy_budget': energy,
                'traffic_name': traffic_name,
                'traffic_interval': traffic_interval,
                'network_lifetime': network_lifetime
            })
            
            # Brief pause between runs
            if current_run < total_runs:
                print(f"\n⏸️  Pausing 2 seconds before next run...")
                time.sleep(2)
    
    # Print summary
    elapsed_total = time.time() - start_time_total
    
    print(f"\n\n{'='*70}")
    print(f"✅ ALL EXPERIMENTS COMPLETED!")
    print(f"{'='*70}")
    print(f"\nTotal time: {elapsed_total/60:.1f} minutes")
    print(f"\nResults Summary:")
    print(f"{'='*70}")
    print(f"{'Energy':<10} {'Traffic':<10} {'Interval':<10} {'Lifetime':<12}")
    print(f"{'-'*70}")
    
    for result in results_summary:
        lifetime_str = f"{result['network_lifetime']:.1f}s" if result['network_lifetime'] else "Failed"
        print(f"{result['energy_budget']:<10} {result['traffic_name']:<10} "
              f"{result['traffic_interval']:<10} {lifetime_str:<12}")
    
    print(f"\n{'='*70}")
    print(f"Now generating plots...")
    print(f"{'='*70}\n")
    
    # Generate plots
    try:
        subprocess.run(
            ['python3', str(BASE_DIR / 'generate_all_plots.py'), '--fig6'],
            check=True
        )
        print("\n✅ Plot generated successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\n⚠️  Error generating plot: {e}")
    
    print(f"\n{'='*70}")
    print(f"Figure 6 experiment complete!")
    print(f"Check 'results_fig6_*' folders for detailed results")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
