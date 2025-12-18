#!/usr/bin/env python3
"""
Multi-scenario experiment runner for Figure 5: Packets Sent vs Delivered.

Runs simulations with different packet loss rates and multiple traffic loads
to generate lines showing packet delivery performance.

For each packet loss rate (0, 0.0001, 0.001):
  - Run with different traffic intervals (10s, 5s, 2s, 1s)
  - Each generates more packets as traffic increases
  - Plot lines connecting these points
"""

import subprocess
import sys
import os
import time
import shutil
from pathlib import Path

def update_config(params):
    """Update config.py with simulation parameters."""
    config_path = Path("wsnlab/source/config.py")
    
    with open(config_path, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        modified = False
        for param, value in params.items():
            if line.startswith(f'{param} ='):
                new_lines.append(f'{param} = {value}\n')
                modified = True
                break
        if not modified:
            new_lines.append(line)
    
    with open(config_path, 'w') as f:
        f.writelines(new_lines)

def run_scenario(packet_loss, traffic_interval, scenario_name):
    """Run a single simulation scenario."""
    print("\n" + "="*70)
    print(f"SCENARIO: {scenario_name}")
    print("="*70)
    print(f"Packet Loss Rate: {packet_loss}")
    print(f"Traffic Interval: {traffic_interval}s")
    print()
    
    # Update configuration
    params = {
        'SIM_DURATION': '3000  # Fig 5',
        f'DATA_PACKET_INTERVAL': f'{traffic_interval}  # Fig 5',
        'PACKET_LOSS_RATE': f'{packet_loss}  # Fig 5',
        'BATTERY_ENERGY_TOTAL': '15.0  # Fig 5: High energy to reach lifetime',
        'BASELINE_CURRENT': '0.0003  # Fig 5: Low baseline',
        'SIM_VISUALIZATION': 'False  # Faster simulation',
        'NUM_NODES_TO_FAIL': '0  # No failures for Fig 5',
    }
    
    update_config(params)
    
    # Run simulation
    print("🚀 Starting simulation...")
    
    try:
        original_dir = os.getcwd()
        os.chdir('wsnlab')
        
        result = subprocess.run(
            [sys.executable, "data_collection_tree.py"],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        os.chdir(original_dir)
        
        if result.returncode != 0:
            print(f"❌ Simulation failed with return code {result.returncode}")
            if result.stderr:
                print("Error:", result.stderr[:500])
            return False
        
        print("✓ Simulation completed")
        
        # Move results
        results_folders = list(Path('wsnlab').glob('results_*'))
        if results_folders:
            latest_result = max(results_folders, key=lambda p: p.stat().st_mtime)
            dest_name = f"results_fig5_{scenario_name}"
            dest = Path('.') / dest_name
            
            if dest.exists():
                shutil.rmtree(dest)
            
            shutil.move(str(latest_result), str(dest))
            print(f"✓ Results saved to: {dest_name}")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Simulation timed out")
        os.chdir(original_dir)
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        os.chdir(original_dir)
        return False

def main():
    """Run all scenarios and generate plot."""
    print("\n" + "="*70)
    print("FIGURE 5 MULTI-SCENARIO EXPERIMENT")
    print("="*70)
    print("""
This experiment runs 12 simulations (3 packet loss rates × 4 traffic loads):

Packet Loss Rates: 0, 0.0001, 0.001
Traffic Intervals: 10s, 5s, 2s, 1s (lower = more packets)

Each simulation generates a data point showing packets sent/delivered
at network lifetime. Lines connect points for each packet loss rate.

Estimated time: ~15-20 minutes
    """)
    print("="*70)
    
    # Define all scenarios
    scenarios = []
    packet_loss_rates = [0, 0.0001, 0.001]
    traffic_intervals = [10, 5, 2, 1]  # seconds
    
    for pl in packet_loss_rates:
        for ti in traffic_intervals:
            pl_str = "pl0" if pl == 0 else f"pl{pl}".replace(".", "p")
            scenario_name = f"{pl_str}_ti{ti}s"
            scenarios.append((pl, ti, scenario_name))
    
    start_time = time.time()
    results = {}
    
    # Run each scenario
    for pl, ti, name in scenarios:
        success = run_scenario(pl, ti, name)
        results[name] = success
        
        if not success:
            print(f"\n⚠️  Scenario '{name}' failed, continuing...")
    
    # Generate plot
    print("\n" + "="*70)
    print("GENERATING FIGURE 5 PLOT")
    print("="*70)
    
    try:
        result = subprocess.run(
            [sys.executable, "generate_all_plots.py", "--fig5"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.stdout:
            print(result.stdout)
        
        if result.returncode == 0:
            print("\n✓ Figure 5 plot generated successfully!")
        else:
            print(f"\n⚠️  Plotting had issues (code {result.returncode})")
            
    except Exception as e:
        print(f"❌ Error generating plot: {e}")
    
    elapsed_time = time.time() - start_time
    
    # Summary
    print("\n" + "="*70)
    print("EXPERIMENT SUMMARY")
    print("="*70)
    
    successful = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, success in results.items():
        status = "✓" if success else "✗"
        print(f"{status} {name}")
    
    print(f"\nCompleted: {successful}/{total} scenarios")
    print(f"Total time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
    print("\nGenerated files:")
    print("  • fig5_packets_sent_vs_delivered.png")
    print("  • results_fig5_*/  (12 folders)")
    print("="*70)
    
    return 0 if successful == total else 1

if __name__ == "__main__":
    sys.exit(main())
