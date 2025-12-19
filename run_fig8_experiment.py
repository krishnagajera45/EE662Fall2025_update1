#!/usr/bin/env python3
"""
Figure 8 Experiment: Network Lifetime vs Initial Energy
Low Traffic vs High Traffic

Runs simulations with varying initial energy (E_0) and traffic loads to measure
network lifetime (time until <80% nodes remain connected to sink).

Experiment Matrix:
- Initial energy (E_0): [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5] Joules (7 values)
- Traffic loads: Low (high interval), High (low interval) (2 values)
- Total: 14 simulation runs

Each simulation runs until network lifetime is reached or max duration.
"""

import subprocess
import os
import time
import json
from pathlib import Path
import sys
import re
import shutil
import glob

# Base directory
BASE_DIR = Path(__file__).parent.absolute()
WSNLAB_DIR = BASE_DIR / "wsnlab"
CONFIG_FILE = WSNLAB_DIR / "source" / "config.py"
SIMULATION_SCRIPT = WSNLAB_DIR / "data_collection_tree.py"

def update_config(initial_energy, traffic_interval, sim_duration=5000):
    """
    Update config.py with specific parameters for Fig 8.
    
    Args:
        initial_energy: Initial energy per node in Joules (E_0)
        traffic_interval: Time between data packets (controls traffic load)
        sim_duration: Simulation duration in seconds
    """
    print(f"\n📝 Updating config.py:")
    print(f"   - Initial energy (E_0): {initial_energy}J")
    print(f"   - Traffic interval: {traffic_interval}s")
    print(f"   - Simulation duration: {sim_duration}s")
    
    with open(CONFIG_FILE, 'r') as f:
        config_content = f.read()
    
    # Update simulation duration
    config_content = re.sub(
        r'SIM_DURATION = \d+.*',
        f'SIM_DURATION = {sim_duration}  # Fig 8: Network lifetime vs initial energy',
        config_content
    )
    
    # Update energy budget
    config_content = re.sub(
        r'BATTERY_ENERGY_TOTAL = [\d.]+.*',
        f'BATTERY_ENERGY_TOTAL = {initial_energy}  # Fig 8: Initial energy E_0',
        config_content
    )
    
    # Update traffic interval
    config_content = re.sub(
        r'DATA_PACKET_INTERVAL = [\d.]+.*',
        f'DATA_PACKET_INTERVAL = {traffic_interval}  # Fig 8: Traffic control',
        config_content
    )
    
    # Use realistic baseline current for energy depletion
    config_content = re.sub(
        r'BASELINE_CURRENT = [\d.]+.*',
        f'BASELINE_CURRENT = 0.03  # Fig 8: Realistic baseline (30mA)',
        config_content
    )
    
    # Disable visualization for speed
    config_content = re.sub(
        r'SIM_VISUALIZATION = (True|False).*',
        'SIM_VISUALIZATION = False  # Fig 8: Faster simulation',
        config_content
    )
    
    # No packet loss
    config_content = re.sub(
        r'PACKET_LOSS_RATE = [\d.]+.*',
        'PACKET_LOSS_RATE = 0  # Fig 8: No artificial loss',
        config_content
    )
    
    # Enable multihop discovery
    config_content = re.sub(
        r'ENABLE_MULTIHOP_DISCOVERY = (True|False).*',
        'ENABLE_MULTIHOP_DISCOVERY = True  # Fig 8: CT+Mesh',
        config_content
    )
    
    with open(CONFIG_FILE, 'w') as f:
        f.write(config_content)
    
    print("   ✓ Config updated")

def run_simulation(scenario_name, initial_energy, traffic_name, traffic_interval):
    """
    Run a single simulation and extract network lifetime.
    
    Args:
        scenario_name: Unique name for this scenario
        initial_energy: Initial energy per node (Joules)
        traffic_name: 'low' or 'high'
        traffic_interval: Time between packets (seconds)
    
    Returns:
        network_lifetime: Time when network lifetime was reached (seconds), or None if failed
    """
    print(f"\n{'='*70}")
    print(f"🚀 Starting simulation: {scenario_name}")
    print(f"   Initial energy (E_0): {initial_energy}J")
    print(f"   Traffic: {traffic_name} (interval: {traffic_interval}s)")
    print(f"{'='*70}\n")
    
    # Update configuration
    update_config(initial_energy, traffic_interval, sim_duration=5000)
    
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
            
            # Save results
            results_folder = BASE_DIR / f"results_fig8_{scenario_name}"
            
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
            
            for pattern in files_to_copy:
                file_path = WSNLAB_DIR / pattern
                if file_path.exists():
                    shutil.copy2(file_path, results_folder / pattern)
            
            # Copy log files
            for log_file in glob.glob(str(WSNLAB_DIR / "wsn_log*.log")):
                shutil.copy2(log_file, results_folder / Path(log_file).name)
            
            # Create metadata
            metadata = {
                'scenario': scenario_name,
                'initial_energy': initial_energy,
                'traffic_load': traffic_name,
                'traffic_interval': traffic_interval,
                'network_lifetime': network_lifetime,
                'sim_duration': 5000,
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
        print(f"\n⏱️  Simulation timed out after 1 hour")
        return None
    except Exception as e:
        print(f"\n❌ Error running simulation: {e}")
        return None

def main():
    """
    Main experiment runner for Figure 8.
    """
    print("\n" + "="*70)
    print("Figure 8 Experiment: Network Lifetime vs Initial Energy")
    print("Low Traffic vs High Traffic")
    print("="*70)
    print("\nThis experiment will:")
    print("  - Vary initial energy (E_0): 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5 J")
    print("  - Test two traffic conditions: Low and High")
    print("  - Measure network lifetime (time until <80% connectivity)")
    print("  - Generate comparison plot")
    print(f"\nEstimated time: 2-3 hours (14 simulations)")
    print("="*70)
    
    # Experiment parameters
    initial_energies = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]  # Joules
    traffic_configs = {
        'low': 20,    # High interval = low traffic
        'high': 5     # Low interval = high traffic
    }
    
    start_time_total = time.time()
    results = {}
    
    # Run all simulations
    for energy in initial_energies:
        for traffic_name, traffic_interval in traffic_configs.items():
            scenario_name = f"E{energy:.1f}J_{traffic_name}"
            
            network_lifetime = run_simulation(
                scenario_name, 
                energy, 
                traffic_name, 
                traffic_interval
            )
            
            if network_lifetime is not None:
                if traffic_name not in results:
                    results[traffic_name] = []
                results[traffic_name].append({
                    'initial_energy': energy,
                    'network_lifetime': network_lifetime
                })
            
            # Pause between simulations
            if energy < initial_energies[-1] or traffic_name == 'low':
                print(f"\n⏸️  Pausing 5 seconds before next simulation...")
                time.sleep(5)
    
    # Summary
    elapsed_total = time.time() - start_time_total
    
    print(f"\n\n{'='*70}")
    print(f"✅ EXPERIMENTS COMPLETED!")
    print(f"{'='*70}")
    print(f"\nTotal time: {elapsed_total/60:.1f} minutes")
    print(f"\nResults summary:")
    
    for traffic_name in ['low', 'high']:
        if traffic_name in results:
            print(f"\n  {traffic_name.upper()} TRAFFIC:")
            for r in sorted(results[traffic_name], key=lambda x: x['initial_energy']):
                print(f"    E_0 = {r['initial_energy']:.1f}J → Lifetime = {r['network_lifetime']:.1f}s")
    
    # Save summary results
    summary_file = BASE_DIR / "results_fig8_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n📊 Summary saved to: {summary_file.name}")
    
    print(f"\n{'='*70}")
    print(f"Now generating plot...")
    print(f"{'='*70}\n")
    
    # Generate plot
    try:
        subprocess.run(
            ['python3', str(BASE_DIR / 'generate_all_plots.py'), '--fig8'],
            check=True
        )
        print("\n✅ Plot generated successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\n⚠️  Error generating plot: {e}")
    
    print(f"\n{'='*70}")
    print(f"Figure 8 experiment complete!")
    print(f"Check 'results_fig8_*' folders for detailed results")
    print(f"Check 'fig8_network_lifetime_vs_initial_energy.png' for the plot")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
