#!/usr/bin/env python3
"""
Script to run Fig. 9 experiment: Average remaining energy over time for different traffic loads.
Runs simulations with different packet generation rates: low, medium, and high traffic.
"""

import subprocess
import sys
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
import time

CONFIG_FILE = "wsnlab/source/config.py"
SIMULATION_SCRIPT = "wsnlab/data_collection_tree.py"

class ConfigModifier:
    """Helper class to modify config.py safely."""
    
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.backup_path = self.config_path.with_suffix('.py.backup')
        self.original_content = None
    
    def backup(self):
        """Backup original config file."""
        if self.config_path.exists():
            self.original_content = self.config_path.read_text()
            shutil.copy2(self.config_path, self.backup_path)
            print(f"  ✓ Backed up config to {self.backup_path}")
    
    def restore(self):
        """Restore original config file."""
        if self.backup_path.exists() and self.original_content:
            self.config_path.write_text(self.original_content)
            self.backup_path.unlink()
            print(f"  ✓ Restored original config")
    
    def set_value(self, var_name, value):
        """Set a configuration variable to a new value."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        content = self.config_path.read_text()
        lines = content.split('\n')
        new_lines = []
        found = False
        
        pattern = rf'^({re.escape(var_name)}\s*=\s*)([^\n#]+?)(\s*#.*)?$'
        
        for line in lines:
            if line.lstrip().startswith('#'):
                new_lines.append(line)
                continue
            
            match = re.match(pattern, line)
            if match:
                comment = match.group(3) if match.group(3) else ""
                new_line = f"{match.group(1)}{value}{comment}"
                new_lines.append(new_line)
                found = True
                print(f"  ✓ Updated {var_name} = {value}")
            else:
                new_lines.append(line)
        
        if not found:
            print(f"  ⚠️  Variable {var_name} not found in config")
            return False
        
        new_content = '\n'.join(new_lines)
        self.config_path.write_text(new_content)
        return True


def run_simulation(traffic_load, packet_interval, run_num, total_runs):
    """Run a single simulation with specified traffic load."""
    print(f"\n{'='*70}")
    print(f"Run {run_num}/{total_runs}: {traffic_load} Traffic Load")
    print(f"Packet Interval: {packet_interval}s")
    print(f"{'='*70}")
    
    try:
        result = subprocess.run(
            [sys.executable, SIMULATION_SCRIPT],
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )
        
        if result.returncode != 0:
            print(f"  ❌ Simulation failed!")
            if result.stderr:
                print(f"  Error: {result.stderr[:300]}")
            return False
        
        print(f"  ✓ Simulation completed")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"  ❌ Simulation timed out!")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def generate_plots():
    """Generate Figure 9 plot."""
    print(f"\n{'='*70}")
    print("GENERATING FIGURE 9 PLOT")
    print(f"{'='*70}")
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", 
             "from generate_all_plots import plot_fig9_avg_remaining_energy_over_time; plot_fig9_avg_remaining_energy_over_time()"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            print(f"  ❌ Plot generation failed!")
            if result.stderr:
                print(f"  Error: {result.stderr[:300]}")
            return False
        
        print(f"  ✓ Figure 9 plot generated successfully")
        return True
        
    except Exception as e:
        print(f"  ❌ Plot generation failed: {e}")
        return False


def main():
    """Main function."""
    print("="*80)
    print("FIG. 9 EXPERIMENT: Average Remaining Energy vs Traffic Load")
    print("="*80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print("\nThis experiment will run 3 simulations with different traffic loads:")
    print("   • Low Traffic:    10s packet interval -> 0.1 packets/s per node")
    print("   • Medium Traffic:  5s packet interval -> 0.2 packets/s per node")
    print("   • High Traffic:    1s packet interval -> 1.0 packets/s per node")
    print("\nEach simulation will track:")
    print("   • Average remaining energy over time")
    print("   • Energy depletion patterns")
    print("   • Network performance under different loads")
    print("   • Power analysis CSV files (friend's style)")
    print("\nEstimated time: 3 simulations (~1-2 hours)")
    print("Output: fig9_avg_remaining_energy_over_time.png")
    print("="*80)
    
    print("\nStarting experiment...")
    
    config_mod = ConfigModifier(CONFIG_FILE)
    config_mod.backup()
    
    # Set base configuration for Fig. 9
    config_mod.set_value("SIM_NODE_COUNT", "100")
    config_mod.set_value("SIM_DURATION", "5000")
    config_mod.set_value("ENABLE_ENERGY_MODEL", "True")
    config_mod.set_value("ENABLE_NODE_FAILURE_RECOVERY", "False")
    config_mod.set_value("ENABLE_NETWORK_SNAPSHOTS", "False")
    config_mod.set_value("SIM_VISUALIZATION", "False")
    
    # Use standard energy and routing
    config_mod.set_value("PACKET_LOSS_RATE", "0")
    config_mod.set_value("ENABLE_MESH_ROUTING", "True")
    config_mod.set_value("ENABLE_TREE_ROUTING", "True")
    config_mod.set_value("BATTERY_VOLTAGE", "3.0")
    config_mod.set_value("BATTERY_CAPACITY", "0.013889")  # 50J energy budget (50J / (3V * 3600s/h))
    
    # Traffic loads to test (packet intervals in seconds)
    traffic_scenarios = [
        ("Low", 10.0),      # 0.1 packets/s per node
        ("Medium", 5.0),    # 0.2 packets/s per node  
        ("High", 1.0),      # 1.0 packets/s per node
    ]
    
    total_runs = len(traffic_scenarios)
    run_num = 0
    successful = 0
    start_time = time.time()
    
    try:
        for traffic_load, packet_interval in traffic_scenarios:
            run_num += 1
            
            print(f"\n  Traffic Load: {traffic_load}")
            print(f"  Packet Interval: {packet_interval}s")
            print(f"  Expected Rate: {1.0/packet_interval:.1f} packets/s per node")
            
            # Update traffic configuration
            config_mod.set_value("DATA_PACKET_INTERVAL", f"{packet_interval}")
            
            # Run simulation
            if run_simulation(traffic_load, packet_interval, run_num, total_runs):
                successful += 1
            
            # Small delay between runs
            time.sleep(2)
        
        # Generate Figure 9 plot
        print(f"\n{'='*70}")
        print(f"All simulations complete: {successful}/{total_runs} successful")
        print(f"Generating Figure 9 plot...")
        print(f"{'='*70}")
        
        plot_success = generate_plots()
        
        elapsed = time.time() - start_time
        print(f"\n{'='*70}")
        print("EXPERIMENT COMPLETE")
        print(f"{'='*70}")
        print(f"Total time: {elapsed/60:.1f} minutes")
        print(f"Successful runs: {successful}/{total_runs}")
        print(f"Plot generated: {'Yes' if plot_success else 'No'}")
        
        if plot_success:
            print(f"\n✓ Check fig9_avg_remaining_energy_over_time.png for results!")
            print(f"  The plot shows how different traffic loads affect:")
            print(f"  - Average remaining energy over time")
            print(f"  - Energy depletion rates")
            print(f"  - Network lifetime under different loads")
        
        print(f"{'='*70}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user!")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        config_mod.restore()


if __name__ == "__main__":
    main()