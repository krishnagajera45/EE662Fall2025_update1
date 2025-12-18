#!/usr/bin/env python3
"""
Multi-scenario experiment runner for Figure 8: PDR under different conditions.

This script runs 4 simulations to show PDR degradation:
1. Baseline - Normal operation (high PDR)
2. Low Energy - Nodes dying causes connectivity loss
3. High Traffic - Network congestion affects delivery
4. Packet Loss - Artificial packet drops in channel
"""

import subprocess
import sys
import os
import time
import shutil
from pathlib import Path

def update_config(scenario_params):
    """Update config.py with scenario-specific parameters."""
    config_path = Path("wsnlab/source/config.py")
    
    # Read current config
    with open(config_path, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        modified = False
        for param, value in scenario_params.items():
            if line.startswith(f'{param} ='):
                new_lines.append(f'{param} = {value}\n')
                modified = True
                break
        if not modified:
            new_lines.append(line)
    
    # Write updated config
    with open(config_path, 'w') as f:
        f.writelines(new_lines)

def run_scenario(scenario_name, scenario_params, scenario_description):
    """Run a single scenario simulation."""
    print("\n" + "="*70)
    print(f"SCENARIO: {scenario_name.upper()}")
    print("="*70)
    print(f"Description: {scenario_description}")
    print("\nParameters:")
    for param, value in scenario_params.items():
        print(f"  • {param} = {value}")
    print()
    
    # Update configuration
    update_config(scenario_params)
    
    # Run simulation
    print("🚀 Starting simulation...")
    
    try:
        # Change to wsnlab directory
        original_dir = os.getcwd()
        os.chdir('wsnlab')
        
        # Run simulation
        result = subprocess.run(
            [sys.executable, "data_collection_tree.py"],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        # Change back
        os.chdir(original_dir)
        
        if result.returncode != 0:
            print(f"❌ Simulation failed with return code {result.returncode}")
            if result.stderr:
                print("Error:", result.stderr[:500])
            return False
        
        print("✓ Simulation completed")
        
        # Find and rename results folder
        results_folders = list(Path('wsnlab').glob('results_*'))
        if results_folders:
            latest_result = max(results_folders, key=lambda p: p.stat().st_mtime)
            dest_name = f"results_fig8_{scenario_name}"
            dest = Path('.') / dest_name
            
            # Remove old results if exists
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
    """Run all scenarios and generate comparative plot."""
    print("\n" + "="*70)
    print("FIGURE 8 MULTI-SCENARIO EXPERIMENT")
    print("="*70)
    print("""
This experiment runs 4 scenarios to demonstrate PDR behavior:

1. BASELINE     - Normal conditions (high PDR expected)
2. LOW_ENERGY   - Node deaths cause connectivity loss
3. HIGH_TRAFFIC - Network congestion affects delivery  
4. PACKET_LOSS  - Artificial channel errors

Each simulation takes ~2 minutes. Total time: ~8-10 minutes.
    """)
    print("="*70)
    
    # Define scenarios
    scenarios = [
        {
            'name': 'baseline',
            'description': 'Normal operation with adequate energy and moderate traffic',
            'params': {
                'SIM_DURATION': '3000  # Baseline',
                'DATA_PACKET_INTERVAL': '2.0  # Moderate traffic',
                'BATTERY_ENERGY_TOTAL': '15.0  # High energy',
                'BASELINE_CURRENT': '0.0003  # Low baseline',
                'PACKET_LOSS_RATE': '0.0  # No loss',
                'SIM_VISUALIZATION': 'False',
            }
        },
        {
            'name': 'low_energy',
            'description': 'Reduced energy causes nodes to die, affecting connectivity',
            'params': {
                'SIM_DURATION': '3000  # Low energy',
                'DATA_PACKET_INTERVAL': '2.0  # Moderate traffic',
                'BATTERY_ENERGY_TOTAL': '4.0  # VERY LOW energy',
                'BASELINE_CURRENT': '0.002  # High baseline',
                'PACKET_LOSS_RATE': '0.0  # No loss',
                'SIM_VISUALIZATION': 'False',
            }
        },
        {
            'name': 'high_traffic',
            'description': 'Heavy traffic load causes congestion and packet drops',
            'params': {
                'SIM_DURATION': '3000  # High traffic',
                'DATA_PACKET_INTERVAL': '0.5  # VERY high traffic',
                'BATTERY_ENERGY_TOTAL': '6.0  # Medium energy',
                'BASELINE_CURRENT': '0.001  # High due to traffic',
                'PACKET_LOSS_RATE': '0.0  # No artificial loss',
                'SIM_VISUALIZATION': 'False',
            }
        },
        {
            'name': 'packet_loss',
            'description': 'Artificial packet loss simulates poor channel conditions',
            'params': {
                'SIM_DURATION': '3000  # Packet loss',
                'DATA_PACKET_INTERVAL': '2.0  # Moderate traffic',
                'BATTERY_ENERGY_TOTAL': '15.0  # High energy',
                'BASELINE_CURRENT': '0.0003  # Low baseline',
                'PACKET_LOSS_RATE': '0.15  # 15% packet loss',
                'SIM_VISUALIZATION': 'False',
            }
        },
    ]
    
    start_time = time.time()
    results = {}
    
    # Run each scenario
    for scenario in scenarios:
        success = run_scenario(
            scenario['name'],
            scenario['params'],
            scenario['description']
        )
        results[scenario['name']] = success
        
        if not success:
            print(f"\n⚠️  Scenario '{scenario['name']}' failed, continuing...")
    
    # Generate comparative plot
    print("\n" + "="*70)
    print("GENERATING FIGURE 8 COMPARATIVE PLOT")
    print("="*70)
    
    try:
        result = subprocess.run(
            [sys.executable, "generate_all_plots.py", "--fig8"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.stdout:
            print(result.stdout)
        
        if result.returncode == 0:
            print("\n✓ Figure 8 plot generated successfully!")
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
        print(f"{status} {name.upper()}")
    
    print(f"\nCompleted: {successful}/{total} scenarios")
    print(f"Total time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
    print("\nGenerated files:")
    print("  • fig8_pdr_over_time.png")
    print("  • results_fig8_baseline/")
    print("  • results_fig8_low_energy/")
    print("  • results_fig8_high_traffic/")
    print("  • results_fig8_packet_loss/")
    print("="*70)
    
    return 0 if successful == total else 1

if __name__ == "__main__":
    sys.exit(main())
