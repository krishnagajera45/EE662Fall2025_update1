#!/usr/bin/env python3
"""
Quick script to run Fig. 2 experiment only (Network Size Variation).
Runs simulations with node counts: 10, 50, 80, 100 for both CT and MT.
Generates plot automatically after all runs complete.
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
        
        # Pattern to match: VAR_NAME = value  # optional comment
        # Match: variable name, optional spaces, =, optional spaces, value (until # or end), optional comment
        pattern = rf'^({re.escape(var_name)}\s*=\s*)([^\n#]+?)(\s*#.*)?$'
        
        for line in lines:
            # Check if this line contains the variable (for debugging)
            if var_name in line and not line.strip().startswith('#'):
                match = re.match(pattern, line)
                if match:
                    # Replace the value, keep the comment
                    comment = match.group(3) if match.group(3) else ""
                    new_line = f"{match.group(1)}{value}{comment}"
                    new_lines.append(new_line)
                    found = True
                    print(f"  ✓ Updated {var_name} = {value}")
                else:
                    # Variable found but pattern didn't match - might be a different format
                    print(f"  ⚠️  Found {var_name} but pattern didn't match: {line.strip()[:60]}")
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        if not found:
            print(f"  ⚠️  Variable {var_name} not found in config")
            # Debug: show similar lines
            for i, line in enumerate(lines[:100], 1):
                if var_name in line:
                    print(f"    Line {i}: {line.strip()[:80]}")
            return False
        
        new_content = '\n'.join(new_lines)
        self.config_path.write_text(new_content)
        return True


def run_simulation(node_count, mesh_enabled, run_num, total_runs):
    """Run a single simulation."""
    strategy = "MT" if mesh_enabled else "CT"
    mesh_hop = "H3" if mesh_enabled else ""
    
    print(f"\n{'='*70}")
    print(f"Run {run_num}/{total_runs}: Node Count = {node_count}, Routing = {strategy}")
    print(f"{'='*70}")
    
    try:
        result = subprocess.run(
            [sys.executable, SIMULATION_SCRIPT],
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
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
            [sys.executable, PLOT_SCRIPT],
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
        # Show which plots were created
        plot_files = list(Path('.').glob('fig*.png'))
        if plot_files:
            print(f"  Generated {len(plot_files)} plot files:")
            for pf in sorted(plot_files):
                print(f"    - {pf.name}")
        return True
        
    except Exception as e:
        print(f"  ❌ Plot generation failed: {e}")
        return False


def main():
    """Main function."""
    print("="*70)
    print("FIG. 2 EXPERIMENT: Network Size Variation")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print("\nThis will run simulations with:")
    print("  - Node counts: 10, 50, 80, 100")
    print("  - Routing: CT (Tree only) and MT (Mesh+Tree)")
    print("  - Total: 8 simulations")
    print("\nAfter all simulations, Fig. 2 plot will be generated automatically.")
    print("="*70)
    
    response = input("\nContinue? (y/n): ").strip().lower()
    if response != 'y':
        print("Cancelled.")
        return
    
    config_mod = ConfigModifier(CONFIG_FILE)
    config_mod.backup()
    
    # Enable visualization so you can see the simulations running
    # (Set to False for faster batch runs without GUI overhead)
    config_mod.set_value("SIM_VISUALIZATION", "True")
    
    node_counts = [10, 50, 80, 100]
    mesh_enabled_values = [False, True]  # CT and MT
    
    total_runs = len(node_counts) * len(mesh_enabled_values)
    run_num = 0
    successful = 0
    start_time = time.time()
    
    try:
        for node_count in node_counts:
            for mesh_enabled in mesh_enabled_values:
                run_num += 1
                
                # Update config
                config_mod.set_value("SIM_NODE_COUNT", str(node_count))
                config_mod.set_value("ENABLE_MESH_ROUTING", str(mesh_enabled))
                
                # Run simulation
                if run_simulation(node_count, mesh_enabled, run_num, total_runs):
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
        print(f"Total time: {elapsed/60:.1f} minutes")
        print(f"Successful runs: {successful}/{total_runs}")
        print(f"Plot generated: {'Yes' if plot_success else 'No'}")
        print(f"\nCheck fig2_avg_join_time_vs_network_size.png for results!")
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
