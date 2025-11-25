#!/usr/bin/env python3
"""
Batch simulation runner for collecting statistics across multiple runs.
Runs the simulation N times and collects aggregate statistics.
"""

import subprocess
import sys
import os
import csv
import json
import statistics
from pathlib import Path
from collections import defaultdict
import shutil

def run_simulation(run_number, output_dir):
    """Run a single simulation and collect results."""
    print(f"\n{'='*70}")
    print(f"Running simulation {run_number}/10...")
    print(f"{'='*70}")
    
    # Create output directory for this run
    run_dir = Path(output_dir) / f"run_{run_number:02d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Backup current CSV files
    csv_files = [
        "registration_log.csv",
        "packet_delays.csv",
        "packet_paths.csv",
        "packet_routes.csv",
        "recovery_events.csv",
        "orphan_events.csv",
        "role_changes.csv",
        "clusterhead_distances.csv",
        "neighbor_distances.csv",
        "multihop_neighbor_table.csv"
    ]
    
    # Run the simulation
    try:
        result = subprocess.run(
            [sys.executable, "wsnlab/data_collection_tree.py"],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if result.returncode != 0:
            print(f"ERROR: Simulation {run_number} failed!")
            print(result.stderr)
            return None
        
        # Copy CSV files to run directory
        for csv_file in csv_files:
            if os.path.exists(csv_file):
                shutil.copy2(csv_file, run_dir / csv_file)
        
        # Extract statistics from output
        stats = extract_statistics(run_dir)
        stats['run_number'] = run_number
        stats['success'] = True
        
        return stats
        
    except subprocess.TimeoutExpired:
        print(f"ERROR: Simulation {run_number} timed out!")
        return {'run_number': run_number, 'success': False}
    except Exception as e:
        print(f"ERROR: Simulation {run_number} failed with exception: {e}")
        return {'run_number': run_number, 'success': False}


def extract_statistics(run_dir):
    """Extract statistics from CSV files."""
    stats = {}
    
    # Registration/Join time statistics
    reg_file = run_dir / "registration_log.csv"
    if reg_file.exists():
        join_times = []
        with open(reg_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    join_times.append(float(row['join_delay']))
                except (ValueError, KeyError):
                    pass
        
        if join_times:
            stats['avg_join_time'] = statistics.mean(join_times)
            stats['min_join_time'] = min(join_times)
            stats['max_join_time'] = max(join_times)
            stats['median_join_time'] = statistics.median(join_times)
            stats['num_registered_nodes'] = len(join_times)
    
    # Packet delay statistics
    delay_file = run_dir / "packet_delays.csv"
    if delay_file.exists():
        delays = []
        with open(delay_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    delays.append(float(row['delay']))
                except (ValueError, KeyError):
                    pass
        
        if delays:
            stats['avg_packet_delay'] = statistics.mean(delays)
            stats['min_packet_delay'] = min(delays)
            stats['max_packet_delay'] = max(delays)
            stats['total_packets'] = len(delays)
    
    # Cluster statistics
    ch_file = run_dir / "clusterhead_distances.csv"
    if ch_file.exists():
        cluster_heads = set()
        with open(ch_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    cluster_heads.add(int(row['clusterhead_1']))
                    cluster_heads.add(int(row['clusterhead_2']))
                except (ValueError, KeyError):
                    pass
        stats['num_clusters'] = len(cluster_heads)
    
    # Role changes
    role_file = run_dir / "role_changes.csv"
    if role_file.exists():
        role_changes = []
        with open(role_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                role_changes.append(row)
        stats['num_role_changes'] = len(role_changes)
    
    # Recovery statistics
    recovery_file = run_dir / "recovery_events.csv"
    if recovery_file.exists():
        recoveries = []
        with open(recovery_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    recoveries.append(float(row['downtime']))
                except (ValueError, KeyError):
                    pass
        if recoveries:
            stats['avg_recovery_time'] = statistics.mean(recoveries)
            stats['num_recoveries'] = len(recoveries)
    
    return stats


def aggregate_statistics(all_stats):
    """Aggregate statistics across all runs."""
    successful_runs = [s for s in all_stats if s.get('success', False)]
    
    if not successful_runs:
        return None
    
    aggregated = {}
    
    # Aggregate join times
    join_times = [s.get('avg_join_time') for s in successful_runs if 'avg_join_time' in s]
    if join_times:
        aggregated['avg_join_time_mean'] = statistics.mean(join_times)
        aggregated['avg_join_time_std'] = statistics.stdev(join_times) if len(join_times) > 1 else 0
        aggregated['avg_join_time_min'] = min(join_times)
        aggregated['avg_join_time_max'] = max(join_times)
    
    # Aggregate packet delays
    packet_delays = [s.get('avg_packet_delay') for s in successful_runs if 'avg_packet_delay' in s]
    if packet_delays:
        aggregated['avg_packet_delay_mean'] = statistics.mean(packet_delays)
        aggregated['avg_packet_delay_std'] = statistics.stdev(packet_delays) if len(packet_delays) > 1 else 0
    
    # Aggregate cluster counts
    cluster_counts = [s.get('num_clusters') for s in successful_runs if 'num_clusters' in s]
    if cluster_counts:
        aggregated['avg_num_clusters'] = statistics.mean(cluster_counts)
        aggregated['num_clusters_std'] = statistics.stdev(cluster_counts) if len(cluster_counts) > 1 else 0
    
    # Aggregate registered nodes
    registered_counts = [s.get('num_registered_nodes') for s in successful_runs if 'num_registered_nodes' in s]
    if registered_counts:
        aggregated['avg_registered_nodes'] = statistics.mean(registered_counts)
    
    aggregated['num_successful_runs'] = len(successful_runs)
    aggregated['num_total_runs'] = len(all_stats)
    
    return aggregated


def main():
    """Main function to run batch simulations."""
    num_runs = 10
    output_dir = "batch_simulation_results"
    
    print("="*70)
    print("BATCH SIMULATION RUNNER")
    print("="*70)
    print(f"Running {num_runs} simulations...")
    print(f"Results will be saved to: {output_dir}/")
    print("="*70)
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    all_stats = []
    
    for run_num in range(1, num_runs + 1):
        stats = run_simulation(run_num, output_dir)
        if stats:
            all_stats.append(stats)
    
    # Save individual run statistics
    stats_file = Path(output_dir) / "individual_run_stats.json"
    with open(stats_file, 'w') as f:
        json.dump(all_stats, f, indent=2)
    
    # Calculate and save aggregated statistics
    aggregated = aggregate_statistics(all_stats)
    if aggregated:
        agg_file = Path(output_dir) / "aggregated_statistics.json"
        with open(agg_file, 'w') as f:
            json.dump(aggregated, f, indent=2)
        
        print("\n" + "="*70)
        print("AGGREGATED STATISTICS (across all runs)")
        print("="*70)
        print(f"Successful runs: {aggregated['num_successful_runs']}/{aggregated['num_total_runs']}")
        if 'avg_join_time_mean' in aggregated:
            print(f"\nAverage Join Time:")
            print(f"  Mean: {aggregated['avg_join_time_mean']:.4f}s")
            print(f"  Std Dev: {aggregated['avg_join_time_std']:.4f}s")
            print(f"  Min: {aggregated['avg_join_time_min']:.4f}s")
            print(f"  Max: {aggregated['avg_join_time_max']:.4f}s")
        if 'avg_packet_delay_mean' in aggregated:
            print(f"\nAverage Packet Delay:")
            print(f"  Mean: {aggregated['avg_packet_delay_mean']:.6f}s")
            print(f"  Std Dev: {aggregated['avg_packet_delay_std']:.6f}s")
        if 'avg_num_clusters' in aggregated:
            print(f"\nAverage Number of Clusters:")
            print(f"  Mean: {aggregated['avg_num_clusters']:.2f}")
            print(f"  Std Dev: {aggregated['num_clusters_std']:.2f}")
        print("="*70)
        print(f"\nResults saved to: {output_dir}/")
        print(f"  - Individual stats: {stats_file}")
        print(f"  - Aggregated stats: {agg_file}")


if __name__ == "__main__":
    main()

