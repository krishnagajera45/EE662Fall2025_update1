#!/usr/bin/env python3
"""
Script to run Fig. 5 experiment: Packets Delivered vs Packets Sent.
Measures network lifetime (time until <80% nodes connected to sink)
for different packet loss rates.

Runs simulations with:
- Different packet loss rates (0, 0.001, 0.0001)
- Different initial energy budgets (varying BATTERY_CAPACITY)
- Different traffic loads (varying DATA_PACKET_INTERVAL)

Generates Fig. 5 plot automatically after all runs complete.
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
PLOT_SCRIPT = "generate_all_plots.py"

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
            # Skip commented-out lines entirely
            if line.lstrip().startswith('#'):
                new_lines.append(line)
                continue

            # Only match lines where the variable appears at the start:  VAR_NAME = ...
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
            for i, line in enumerate(lines[:100], 1):
                if var_name in line:
                    print(f"    Line {i}: {line.strip()[:80]}")
            return False
        
        new_content = '\n'.join(new_lines)
        self.config_path.write_text(new_content)
        return True


def run_simulation(packet_loss, battery_capacity, data_interval, run_num, total_runs):
    """Run a single simulation."""
    
    # Calculate initial energy
    battery_voltage = 3.0
    initial_energy = battery_voltage * battery_capacity * 3600 / 1000  # Joules
    
    traffic_label = "Low" if data_interval >= 30 else ("Medium" if data_interval >= 15 else "High")
    
    print(f"\n{'='*70}")
    print(f"Run {run_num}/{total_runs}: PktLoss={packet_loss}, E₀={initial_energy:.0f}J ({battery_capacity}mAh), Traffic={traffic_label} ({data_interval}s)")
    print(f"{'='*70}")
    
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
    """Generate all plots."""
    print(f"\n{'='*70}")
    print("GENERATING PLOTS")
    print(f"{'='*70}")
    
    try:
        result = subprocess.run(
            [sys.executable, PLOT_SCRIPT, "--fig5"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            print(f"  ❌ Plot generation failed!")
            if result.stderr:
                print(f"  Error: {result.stderr[:300]}")
            return False
        
        print(f"  ✓ Plots generated successfully")
        plot_files = list(Path('.').glob('fig5*.png'))
        if plot_files:
            print(f"  Generated: {plot_files[0].name}")
        return True
        
    except Exception as e:
        print(f"  ❌ Plot generation failed: {e}")
        return False


def main():
    """Main function."""
    print("="*70)
    print("FIG. 5 EXPERIMENT: Packets Delivered vs Packets Sent")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print("\nThis will run simulations with:")
    print("  - Packet Loss Rates: 0, 0.001, 0.0001")
    print("  - Initial Energy (E₀): 500, 2000 mAh")
    print("    (corresponds to: 5400, 21600 Joules)")
    print("  - Traffic Loads:")
    print("    - Low traffic: DATA_PACKET_INTERVAL = 60s")
    print("    - High traffic: DATA_PACKET_INTERVAL = 10s")
    print("  - Routing: Mesh+Tree (hybrid)")
    print("  - Baseline Current: 100 mA (for faster energy depletion)")
    print("  - Total: 12 simulations (3 packet loss × 2 energy × 2 traffic)")
    print("\nNetwork lifetime = time until <80% nodes remain connected to sink")
    print("After all simulations, Fig. 5 plot will be generated automatically.")
    print("="*70)
    
    # Check if running in interactive mode
    import sys
    if sys.stdin.isatty():
    response = input("\nContinue? (y/n): ").strip().lower()
    if response != 'y':
        print("Cancelled.")
        return
    else:
        print("\nAuto-starting (non-interactive mode)...")
    
    config_mod = ConfigModifier(CONFIG_FILE)
    config_mod.backup()
    
    try:
        # Set base configuration
        config_mod.set_value("SIM_NODE_COUNT", "100")
        config_mod.set_value("ENABLE_ENERGY_MODEL", "True")
        config_mod.set_value("ENABLE_NODE_FAILURE_RECOVERY", "False")
        config_mod.set_value("NUM_NODES_TO_FAIL", "0")  # Explicitly set to 0 for Fig 5
        config_mod.set_value("ENABLE_NETWORK_SNAPSHOTS", "False")
        config_mod.set_value("SNAPSHOT_PERIODIC_ENABLED", "True")  # Enable periodic tracking for connectivity
        config_mod.set_value("SNAPSHOT_PERIODIC_INTERVAL", "100")  # Check every 100 seconds
        config_mod.set_value("SIM_VISUALIZATION", "False")
        config_mod.set_value("ENABLE_MESH_ROUTING", "True")  # Always use Mesh+Tree
        
        # Packet loss rates
        packet_loss_rates = [0, 0.001, 0.0001]
        
        # Energy budgets (mAh) - 2 levels for 12 total simulations
        battery_capacities = [500, 2000]
        
        # Traffic loads
        data_intervals = {
            'Low': 60,   # Send every 60 seconds
            'High': 10   # Send every 10 seconds
        }
        
        total_runs = len(packet_loss_rates) * len(battery_capacities) * len(data_intervals)
        run_num = 0
        successful = 0
        start_time = time.time()
        
        for packet_loss in packet_loss_rates:
            config_mod.set_value("PACKET_LOSS_RATE", str(packet_loss))
            
            for battery_capacity in battery_capacities:
                config_mod.set_value("BATTERY_CAPACITY", str(battery_capacity))
                
                for traffic_label, data_interval in data_intervals.items():
                    run_num += 1
                    config_mod.set_value("DATA_PACKET_INTERVAL", str(data_interval))
                    
                    # Run simulation
                    if run_simulation(packet_loss, battery_capacity, data_interval, run_num, total_runs):
                        successful += 1
                    
                    # Small delay between runs
                    time.sleep(1)
        
        # Generate plots
        print(f"\n{'='*70}")
        print(f"All simulations complete: {successful}/{total_runs} successful")
        print(f"Generating plots...")
        print(f"{'='*70}")
        
        plot_success = generate_plots()
        
        elapsed = time.time() - start_time
        print(f"\n{'='*70}")
        print("EXPERIMENT COMPLETE")
        print(f"{'='*70}")
        print(f"Total time: {elapsed/60:.1f} minutes ({elapsed/3600:.2f} hours)")
        print(f"Successful runs: {successful}/{total_runs}")
        print(f"Plot generated: {'Yes' if plot_success else 'No'}")
        print(f"\nCheck fig5_packets_delivered_vs_sent.png for results!")
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
