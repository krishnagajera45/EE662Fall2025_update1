#!/usr/bin/env python3
"""
Script to run Fig. 7 experiment: Impact of initial energy budget on lifetime metrics.
Runs simulations with 4 different energy budgets: 0.5J, 1.0J, 2.0J, 3.0J
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


def run_simulation(energy_budget, run_num, total_runs):
    """Run a single simulation with specified energy budget."""
    print(f"\n{'='*70}")
    print(f"Run {run_num}/{total_runs}: Energy Budget = {energy_budget}J")
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
    """Generate Figure 7 plot."""
    print(f"\n{'='*70}")
    print("GENERATING FIGURE 7 PLOT")
    print(f"{'='*70}")
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", 
             "from generate_all_plots import plot_fig7_energy_impact_on_lifetime_metrics; plot_fig7_energy_impact_on_lifetime_metrics()"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            print(f"  ❌ Plot generation failed!")
            if result.stderr:
                print(f"  Error: {result.stderr[:300]}")
            return False
        
        print(f"  ✓ Figure 7 plot generated successfully")
        return True
        
    except Exception as e:
        print(f"  ❌ Plot generation failed: {e}")
        return False


def main():
    """Main function."""
    print("="*70)
    print("FIG. 7 EXPERIMENT: Impact of Initial Energy Budget on Lifetime Metrics")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print("\nThis will run simulations with 4 different energy budgets:")
    print("  - 10J (very low energy - early deaths)")
    print("  - 20J (low energy - moderate deaths)")
    print("  - 50J (medium energy - later deaths)")
    print("  - 100J (higher energy - latest deaths)")
    print("\nEach simulation will track:")
    print("  - First node death time")
    print("  - 50% nodes dead time")
    print("  - Network connectivity drop time")
    print("\nTotal: 4 simulations (~2-3 hours)")
    print("="*70)
    
    print("\nStarting experiment...")
    
    config_mod = ConfigModifier(CONFIG_FILE)
    config_mod.backup()
    
    # Set base configuration for Fig. 7
    config_mod.set_value("SIM_NODE_COUNT", "100")
    config_mod.set_value("SIM_DURATION", "5000")
    config_mod.set_value("ENABLE_ENERGY_MODEL", "True")
    config_mod.set_value("ENABLE_NODE_FAILURE_RECOVERY", "False")
    config_mod.set_value("ENABLE_NETWORK_SNAPSHOTS", "False")
    config_mod.set_value("SIM_VISUALIZATION", "False")
    
    # Use standard traffic and routing
    config_mod.set_value("DATA_PACKET_INTERVAL", "1.0")
    config_mod.set_value("PACKET_LOSS_RATE", "0")
    config_mod.set_value("ENABLE_MESH_ROUTING", "True")
    config_mod.set_value("ENABLE_TREE_ROUTING", "True")
    config_mod.set_value("BATTERY_VOLTAGE", "3.0")
    
    # Energy budgets to test (in Joules) - much lower values to see node deaths
    # These values will cause nodes to die during the 5000s simulation
    energy_budgets = [10, 20, 50, 100]  # Very low energy budgets to see death patterns
    
    total_runs = len(energy_budgets)
    run_num = 0
    successful = 0
    start_time = time.time()
    
    try:
        for energy_budget in energy_budgets:
            run_num += 1
            
            # Convert energy budget to battery capacity
            # Energy (J) = Capacity (Ah) × Voltage (V) × 3600 (s/h)
            # Capacity (Ah) = Energy (J) / (Voltage × 3600)
            voltage = 3.0
            capacity_ah = energy_budget / (voltage * 3600)
            
            print(f"\n  Energy Budget: {energy_budget}J")
            print(f"  Battery Capacity: {capacity_ah:.6f} Ah")
            print(f"  Battery Voltage: {voltage} V")
            
            # Update energy configuration
            config_mod.set_value("BATTERY_CAPACITY", f"{capacity_ah:.6f}")
            
            # Run simulation
            if run_simulation(energy_budget, run_num, total_runs):
                successful += 1
            
            # Small delay between runs
            time.sleep(2)
        
        # Generate Figure 7 plot
        print(f"\n{'='*70}")
        print(f"All simulations complete: {successful}/{total_runs} successful")
        print(f"Generating Figure 7 plot...")
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
            print(f"\n✓ Check fig7_energy_impact_on_lifetime_metrics.png for results!")
            print(f"  The plot shows how different energy budgets affect:")
            print(f"  - First node death time (blue bars)")
            print(f"  - 50% nodes dead time (red bars)")
            print(f"  - Network connectivity drop time (brown bars)")
        
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