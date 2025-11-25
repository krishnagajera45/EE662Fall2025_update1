#!/usr/bin/env python3
"""
Comprehensive plotting script for WSN protocol analysis.
All plotting functions consolidated into a single file.
"""

import csv
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
import statistics
import re
import json
import subprocess
import sys
import shutil
import time

# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

def load_join_times(csv_file="registration_log.csv"):
    """Load join times from registration log."""
    join_times = []
    node_ids = []
    
    if not Path(csv_file).exists():
        return join_times, node_ids
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                join_time = float(row['join_delay'])
                node_id = int(row['node_id'])
                join_times.append(join_time)
                node_ids.append(node_id)
            except (ValueError, KeyError):
                continue
    
    return join_times, node_ids


def load_packet_paths(csv_file="packet_paths.csv", max_packets=100):
    """Load packet paths from CSV."""
    paths = []
    
    if not Path(csv_file).exists():
        return paths
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= max_packets:
                break
            try:
                path_str = row.get('path', '')
                path_nodes = [int(n) for n in path_str.split('->') if n.strip().isdigit()]
                if len(path_nodes) >= 2:
                    paths.append({
                        'packet_id': row.get('packet_id', ''),
                        'source': int(row.get('source_gui', 0)),
                        'dest': int(row.get('dest_gui', 0)),
                        'path': path_nodes,
                        'hop_count': int(row.get('hop_count', 0)),
                        'delay': float(row.get('delay', 0))
                    })
            except (ValueError, KeyError):
                continue
    
    return paths


def load_node_positions():
    """Load node positions."""
    positions = {}
    
    if Path("node_distances.csv").exists():
        nodes = set()
        with open("node_distances.csv", 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                nodes.add(int(row['source_id']))
                nodes.add(int(row['target_id']))
        
        n = len(nodes)
        edge = int(np.ceil(np.sqrt(n)))
        for i, node_id in enumerate(sorted(nodes)):
            x = (i % edge) * 100
            y = (i // edge) * 100
            positions[node_id] = (x, y)
    else:
        for i in range(100):
            x = (i % 10) * 100
            y = (i // 10) * 100
            positions[i] = (x, y)
    
    return positions


def load_all_metrics():
    """Load all available metrics from CSV files."""
    metrics = {}
    
    if Path("registration_log.csv").exists():
        join_times = []
        with open("registration_log.csv", 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    join_times.append(float(row['join_delay']))
                except (ValueError, KeyError):
                    pass
        metrics['join_times'] = join_times
    
    if Path("packet_delays.csv").exists():
        delays = []
        with open("packet_delays.csv", 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    delays.append(float(row['delay']))
                except (ValueError, KeyError):
                    pass
        metrics['packet_delays'] = delays
    
    if Path("role_changes.csv").exists():
        role_changes = []
        with open("role_changes.csv", 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                role_changes.append(row)
        metrics['role_changes'] = role_changes
    
    if Path("recovery_events.csv").exists():
        recoveries = []
        with open("recovery_events.csv", 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                recoveries.append(row)
        metrics['recoveries'] = recoveries
    
    if Path("orphan_events.csv").exists():
        orphans = []
        with open("orphan_events.csv", 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                orphans.append(row)
        metrics['orphans'] = orphans
    
    if Path("clusterhead_distances.csv").exists():
        cluster_heads = set()
        with open("clusterhead_distances.csv", 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    cluster_heads.add(int(row['clusterhead_1']))
                    cluster_heads.add(int(row['clusterhead_2']))
                except (ValueError, KeyError):
                    pass
        metrics['cluster_heads'] = list(cluster_heads)
    
    return metrics


def load_config_parameters():
    """Load configuration parameters from config.py."""
    config_file = Path("wsnlab/source/config.py")
    if not config_file.exists():
        return None
    
    params = {}
    
    with open(config_file, 'r') as f:
        content = f.read()
        
        patterns = {
            'MAX_CHILD_NODES_ALLOWED_PER_CLUSTER': r'MAX_CHILD_NODES_ALLOWED_PER_CLUSTER\s*=\s*(\d+)',
            'NODE_TX_RANGE': r'NODE_TX_RANGE\s*=\s*(\d+)',
            'HEARTH_BEAT_TIME_INTERVAL': r'HEARTH_BEAT_TIME_INTERVAL\s*=\s*(\d+)',
            'PACKET_LOSS_RATE': r'PACKET_LOSS_RATE\s*=\s*([\d.]+)',
            'SIM_NODE_COUNT': r'SIM_NODE_COUNT\s*=\s*(\d+)',
            'SIM_DURATION': r'SIM_DURATION\s*=\s*(\d+)',
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                try:
                    params[key] = float(match.group(1))
                except ValueError:
                    pass
    
    return params


# ============================================================================
# PLOTTING FUNCTIONS
# ============================================================================

def plot_join_time_analysis():
    """Plot join time analysis."""
    print("  Generating join time analysis plots...")
    join_times, node_ids = load_join_times()
    
    if not join_times:
        print("    Warning: No join time data found")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Network Join Time Analysis', fontsize=16, fontweight='bold')
    
    # Histogram
    axes[0, 0].hist(join_times, bins=30, edgecolor='black', alpha=0.7, color='skyblue')
    axes[0, 0].set_xlabel('Join Time (seconds)')
    axes[0, 0].set_ylabel('Number of Nodes')
    axes[0, 0].set_title('Distribution of Join Times')
    axes[0, 0].axvline(statistics.mean(join_times), color='red', linestyle='--', 
                       label=f'Mean: {statistics.mean(join_times):.2f}s')
    axes[0, 0].axvline(statistics.median(join_times), color='green', linestyle='--', 
                       label=f'Median: {statistics.median(join_times):.2f}s')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # CDF
    sorted_times = sorted(join_times)
    y = np.arange(1, len(sorted_times) + 1) / len(sorted_times)
    axes[0, 1].plot(sorted_times, y, linewidth=2, color='blue')
    axes[0, 1].set_xlabel('Join Time (seconds)')
    axes[0, 1].set_ylabel('Cumulative Probability')
    axes[0, 1].set_title('CDF of Join Times')
    axes[0, 1].grid(True, alpha=0.3)
    
    # Join time vs Node ID
    node_indices = list(range(len(join_times)))
    axes[1, 0].scatter(node_indices, join_times, alpha=0.6, s=30, color='purple')
    axes[1, 0].set_xlabel('Node Index (order of registration)')
    axes[1, 0].set_ylabel('Join Time (seconds)')
    axes[1, 0].set_title('Join Time vs Node Registration Order')
    axes[1, 0].grid(True, alpha=0.3)
    
    # Box plot
    bp = axes[1, 1].boxplot(join_times, vert=True, patch_artist=True)
    bp['boxes'][0].set_facecolor('lightblue')
    axes[1, 1].set_ylabel('Join Time (seconds)')
    axes[1, 1].set_title('Join Time Box Plot')
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].set_xticklabels(['All Nodes'])
    
    plt.tight_layout()
    plt.savefig("join_time_analysis.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("    ✓ Saved: join_time_analysis.png")


def plot_cluster_analysis():
    """Plot cluster size vs number of clusters."""
    print("  Generating cluster analysis plots...")
    
    # Analyze cluster sizes
    num_clusters = 0
    cluster_sizes = []
    
    if Path("role_changes.csv").exists():
        cluster_heads = set()
        with open("role_changes.csv", 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['new_role'] == 'CLUSTER_HEAD':
                    try:
                        cluster_heads.add(int(row['node_id']))
                    except (ValueError, KeyError):
                        pass
        num_clusters = len(cluster_heads)
    
    total_nodes = 0
    if Path("registration_log.csv").exists():
        with open("registration_log.csv", 'r') as f:
            reader = csv.DictReader(f)
            total_nodes = sum(1 for _ in reader)
    
    if num_clusters > 0:
        avg_size = total_nodes / num_clusters
        cluster_sizes = [avg_size] * num_clusters
    
    if num_clusters == 0:
        print("    Warning: No cluster data found")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Cluster Formation Analysis', fontsize=16, fontweight='bold')
    
    # Cluster size distribution
    axes[0, 0].hist(cluster_sizes, bins=max(10, len(set(cluster_sizes))), 
                    edgecolor='black', alpha=0.7, color='lightblue')
    axes[0, 0].set_xlabel('Cluster Size (number of nodes)')
    axes[0, 0].set_ylabel('Number of Clusters')
    axes[0, 0].set_title('Distribution of Cluster Sizes')
    if cluster_sizes:
        axes[0, 0].axvline(statistics.mean(cluster_sizes), color='red', linestyle='--',
                          label=f'Mean: {statistics.mean(cluster_sizes):.1f}')
        axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # Max cluster size vs number of clusters
    max_sizes = range(5, 51, 5)
    estimated_cluster_counts = []
    for max_size in max_sizes:
        estimated_count = int(np.ceil(total_nodes / max_size))
        estimated_cluster_counts.append(estimated_count)
    
    axes[0, 1].plot(max_sizes, estimated_cluster_counts, 'o-', linewidth=2, 
                    markersize=8, color='green')
    axes[0, 1].set_xlabel('Max Nodes per Cluster')
    axes[0, 1].set_ylabel('Estimated Number of Clusters')
    axes[0, 1].set_title('Cluster Count vs Max Cluster Size')
    axes[0, 1].grid(True, alpha=0.3)
    
    # Current configuration
    params = load_config_parameters()
    if params and 'MAX_CHILD_NODES_ALLOWED_PER_CLUSTER' in params:
        current_max = int(params['MAX_CHILD_NODES_ALLOWED_PER_CLUSTER'])
        current_clusters = int(np.ceil(total_nodes / current_max))
        axes[0, 1].axvline(current_max, color='red', linestyle='--', 
                          label=f'Current: {current_max}')
        axes[0, 1].legend()
    
    # Cluster sizes
    cluster_indices = list(range(1, len(cluster_sizes) + 1))
    axes[1, 0].bar(cluster_indices, cluster_sizes, alpha=0.7, color='steelblue', edgecolor='black')
    axes[1, 0].set_xlabel('Cluster Index')
    axes[1, 0].set_ylabel('Cluster Size (nodes)')
    axes[1, 0].set_title('Cluster Sizes')
    axes[1, 0].grid(True, alpha=0.3, axis='y')
    
    # Statistics
    if cluster_sizes:
        stats_text = f"""
        Total Clusters: {num_clusters}
        Total Nodes: {sum(cluster_sizes):.0f}
        Avg Cluster Size: {statistics.mean(cluster_sizes):.2f}
        Min Cluster Size: {min(cluster_sizes):.2f}
        Max Cluster Size: {max(cluster_sizes):.2f}
        Std Dev: {statistics.stdev(cluster_sizes) if len(cluster_sizes) > 1 else 0:.2f}
        """
        axes[1, 1].text(0.1, 0.5, stats_text, fontsize=12, 
                       verticalalignment='center', family='monospace',
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        axes[1, 1].axis('off')
        axes[1, 1].set_title('Cluster Statistics')
    
    plt.tight_layout()
    plt.savefig("cluster_analysis.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("    ✓ Saved: cluster_analysis.png")


def plot_tx_power_analysis():
    """Plot TX power analysis."""
    print("  Generating TX power analysis plots...")
    
    config_file = Path("wsnlab/source/config.py")
    if not config_file.exists():
        print("    Warning: config.py not found")
        return
    
    tx_power_levels = {}
    tx_power_choices = []
    
    with open(config_file, 'r') as f:
        content = f.read()
        match = re.search(r'TX_POWER_LEVELS\s*=\s*\{([^}]+)\}', content)
        if match:
            levels_str = match.group(1)
            for line in levels_str.split('\n'):
                match = re.search(r'(-?\d+):\s*(\d+\.?\d*)', line)
                if match:
                    power = int(match.group(1))
                    current = float(match.group(2))
                    tx_power_levels[power] = current
        
        match = re.search(r'TX_POWER_CHOICES\s*=\s*\[([^\]]+)\]', content)
        if match:
            choices_str = match.group(1)
            for val in choices_str.split(','):
                try:
                    tx_power_choices.append(int(val.strip()))
                except ValueError:
                    pass
    
    if not tx_power_levels:
        print("    Warning: Could not extract TX power levels")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('TX Power Analysis', fontsize=16, fontweight='bold')
    
    # TX Power vs Current
    powers = sorted(tx_power_levels.keys())
    currents = [tx_power_levels[p] for p in powers]
    
    axes[0, 0].plot(powers, currents, 'o-', linewidth=2, markersize=10, color='blue')
    axes[0, 0].set_xlabel('TX Power (dBm)', fontsize=12)
    axes[0, 0].set_ylabel('Current Consumption (mA)', fontsize=12)
    axes[0, 0].set_title('TX Power vs Current Consumption (CC2420)', fontsize=14)
    axes[0, 0].grid(True, alpha=0.3)
    for p, c in zip(powers, currents):
        axes[0, 0].annotate(f'{c:.1f}mA', (p, c), 
                           textcoords="offset points", xytext=(0,10), ha='center')
    
    # TX Power Choices
    if tx_power_choices:
        axes[0, 1].bar(range(len(tx_power_choices)), tx_power_choices, 
                      color='orange', alpha=0.7, edgecolor='black')
        axes[0, 1].set_xticks(range(len(tx_power_choices)))
        axes[0, 1].set_xticklabels([f'Level {i+1}' for i in range(len(tx_power_choices))])
        axes[0, 1].set_ylabel('TX Power (dBm)', fontsize=12)
        axes[0, 1].set_title('Available TX Power Levels', fontsize=14)
        axes[0, 1].grid(True, alpha=0.3, axis='y')
        for i, power in enumerate(tx_power_choices):
            axes[0, 1].text(i, power, f'{power} dBm', ha='center', va='bottom', fontweight='bold')
    
    # Energy vs TX Power
    voltage = 3.0
    packet_size_bytes = 50
    data_rate = 250000
    packet_time = (packet_size_bytes * 8) / data_rate
    
    energies = []
    for p in powers:
        current_ma = tx_power_levels[p]
        current_a = current_ma / 1000.0
        energy = voltage * current_a * packet_time * 1000000
        energies.append(energy)
    
    axes[1, 0].plot(powers, energies, 's-', linewidth=2, markersize=10, color='red')
    axes[1, 0].set_xlabel('TX Power (dBm)', fontsize=12)
    axes[1, 0].set_ylabel('Energy per Packet (µJ)', fontsize=12)
    axes[1, 0].set_title('TX Power vs Energy Consumption per Packet', fontsize=14)
    axes[1, 0].grid(True, alpha=0.3)
    for p, e in zip(powers, energies):
        axes[1, 0].annotate(f'{e:.1f}µJ', (p, e), 
                           textcoords="offset points", xytext=(0,10), ha='center')
    
    # Summary
    summary_text = f"TX Power Configuration\n" + "="*30 + "\n\n"
    summary_text += f"Available Levels: {len(tx_power_levels)}\n"
    summary_text += f"Power Range: {min(powers)} to {max(powers)} dBm\n"
    if tx_power_choices:
        summary_text += f"Choices: {tx_power_choices}\n"
    axes[1, 1].text(0.1, 0.5, summary_text, fontsize=12, 
                   verticalalignment='center', family='monospace',
                   bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    axes[1, 1].axis('off')
    axes[1, 1].set_title('TX Power Summary', fontsize=14)
    
    plt.tight_layout()
    plt.savefig("tx_power_analysis.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("    ✓ Saved: tx_power_analysis.png")


def plot_network_lifetime():
    """Plot network lifetime vs packet size."""
    print("  Generating network lifetime analysis plots...")
    
    battery_energy = 21600
    voltage = 3.0
    data_rate = 250000
    rx_current = 18.8e-3
    baseline_current = 0.0001
    
    tx_powers = [-25, -15, -10, -5, 0]
    tx_currents = [8.5e-3, 9.9e-3, 11.0e-3, 14.0e-3, 17.4e-3]
    
    packet_sizes = np.arange(20, 201, 10)
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Network Lifetime vs Packet Size Analysis', fontsize=16, fontweight='bold')
    
    # Lifetime vs Packet Size
    for tx_power, tx_current in zip(tx_powers, tx_currents):
        lifetimes = []
        for psize in packet_sizes:
            packet_time = (psize * 8) / data_rate
            tx_energy = voltage * tx_current * packet_time
            rx_energy = voltage * rx_current * packet_time
            energy_per_second = tx_energy + rx_energy + (voltage * baseline_current)
            lifetime_seconds = battery_energy / energy_per_second
            lifetime_hours = lifetime_seconds / 3600
            lifetimes.append(lifetime_hours)
        
        axes[0, 0].plot(packet_sizes, lifetimes, 'o-', linewidth=2, 
                       label=f'{tx_power} dBm', markersize=4)
    
    axes[0, 0].set_xlabel('Packet Size (bytes)', fontsize=12)
    axes[0, 0].set_ylabel('Network Lifetime (hours)', fontsize=12)
    axes[0, 0].set_title('Network Lifetime vs Packet Size\n(Different TX Power Levels)', fontsize=14)
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # Energy per packet
    packet_sizes_plot = np.arange(20, 201, 5)
    energies_tx = []
    energies_rx = []
    
    for psize in packet_sizes_plot:
        packet_time = (psize * 8) / data_rate
        tx_energy = voltage * tx_currents[-1] * packet_time * 1e6
        rx_energy = voltage * rx_current * packet_time * 1e6
        energies_tx.append(tx_energy)
        energies_rx.append(rx_energy)
    
    axes[0, 1].plot(packet_sizes_plot, energies_tx, 'o-', linewidth=2, 
                   label='TX Energy (0 dBm)', color='red', markersize=4)
    axes[0, 1].plot(packet_sizes_plot, energies_rx, 's-', linewidth=2, 
                   label='RX Energy', color='blue', markersize=4)
    axes[0, 1].set_xlabel('Packet Size (bytes)', fontsize=12)
    axes[0, 1].set_ylabel('Energy per Packet (µJ)', fontsize=12)
    axes[0, 1].set_title('Energy Consumption per Packet', fontsize=14)
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    
    # Packet rate vs lifetime
    packet_rates = np.arange(0.1, 10.1, 0.1)
    avg_packet_size = 50
    packet_time = (avg_packet_size * 8) / data_rate
    tx_current = tx_currents[-1]
    
    lifetimes_rate = []
    for rate in packet_rates:
        tx_energy_per_sec = voltage * tx_current * packet_time * rate
        rx_energy_per_sec = voltage * rx_current * packet_time * rate
        total_energy_per_sec = tx_energy_per_sec + rx_energy_per_sec + (voltage * baseline_current)
        lifetime_seconds = battery_energy / total_energy_per_sec
        lifetime_hours = lifetime_seconds / 3600
        lifetimes_rate.append(lifetime_hours)
    
    axes[1, 0].plot(packet_rates, lifetimes_rate, linewidth=2, color='green')
    axes[1, 0].set_xlabel('Packet Rate (packets/second)', fontsize=12)
    axes[1, 0].set_ylabel('Network Lifetime (hours)', fontsize=12)
    axes[1, 0].set_title('Network Lifetime vs Packet Rate\n(Avg packet size: 50 bytes)', fontsize=14)
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].set_xscale('log')
    
    # Summary
    stats_text = f"""
    Battery Energy: {battery_energy/1000:.1f} kJ
    Voltage: {voltage}V
    Data Rate: {data_rate/1000:.0f} kbps
    
    Theoretical Lifetime:
    (at 1 packet/sec, 0 dBm TX, 50 bytes):
    ~{battery_energy / (voltage * (tx_currents[-1] + rx_current + baseline_current) * (avg_packet_size * 8 / data_rate)) / 3600:.1f} hours
    """
    axes[1, 1].text(0.5, 0.5, stats_text, ha='center', va='center', 
                   fontsize=11, family='monospace',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    axes[1, 1].axis('off')
    axes[1, 1].set_title('Network Lifetime Summary', fontsize=14)
    
    plt.tight_layout()
    plt.savefig("network_lifetime.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("    ✓ Saved: network_lifetime.png")


def plot_packet_tracing():
    """Plot packet tracing visualization."""
    print("  Generating packet tracing plots...")
    
    paths = load_packet_paths()
    positions = load_node_positions()
    
    if not paths:
        print("    Warning: No packet paths found")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Packet Tracing Analysis', fontsize=16, fontweight='bold')
    
    paths_to_plot = paths[:20]
    
    # Network topology with traces
    ax = axes[0, 0]
    for node_id, (x, y) in positions.items():
        ax.plot(x, y, 'ko', markersize=8, alpha=0.5)
        ax.text(x, y, str(node_id), fontsize=6, ha='center', va='center')
    
    colors = plt.cm.tab20(np.linspace(0, 1, len(paths_to_plot)))
    for i, path_data in enumerate(paths_to_plot):
        path = path_data['path']
        if len(path) < 2:
            continue
        color = colors[i]
        for j in range(len(path) - 1):
            node1, node2 = path[j], path[j + 1]
            if node1 in positions and node2 in positions:
                x1, y1 = positions[node1]
                x2, y2 = positions[node2]
                ax.plot([x1, x2], [y1, y2], '-', color=color, alpha=0.6, linewidth=1.5)
        if path[0] in positions:
            x, y = positions[path[0]]
            ax.plot(x, y, 'go', markersize=12, markeredgecolor='black', markeredgewidth=1)
        if path[-1] in positions:
            x, y = positions[path[-1]]
            ax.plot(x, y, 'ro', markersize=12, markeredgecolor='black', markeredgewidth=1)
    
    ax.set_xlabel('X Position', fontsize=12)
    ax.set_ylabel('Y Position', fontsize=12)
    ax.set_title(f'Packet Traces (showing {len(paths_to_plot)} packets)', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    
    # Hop count distribution
    hop_counts = [p['hop_count'] for p in paths]
    if hop_counts:
        axes[0, 1].hist(hop_counts, bins=range(max(hop_counts) + 2), 
                       edgecolor='black', alpha=0.7, color='skyblue')
        axes[0, 1].set_xlabel('Hop Count', fontsize=12)
        axes[0, 1].set_ylabel('Number of Packets', fontsize=12)
        axes[0, 1].set_title('Distribution of Packet Hop Counts', fontsize=14)
        axes[0, 1].grid(True, alpha=0.3, axis='y')
        mean_hops = statistics.mean(hop_counts)
        axes[0, 1].axvline(mean_hops, color='red', linestyle='--', 
                          label=f'Mean: {mean_hops:.2f}')
        axes[0, 1].legend()
    
    # Delay vs hop count
    delays = [p['delay'] for p in paths]
    if delays and hop_counts:
        axes[1, 0].scatter(hop_counts, delays, alpha=0.6, s=50, color='purple')
        axes[1, 0].set_xlabel('Hop Count', fontsize=12)
        axes[1, 0].set_ylabel('Packet Delay (seconds)', fontsize=12)
        axes[1, 0].set_title('Packet Delay vs Hop Count', fontsize=14)
        axes[1, 0].grid(True, alpha=0.3)
        if len(hop_counts) > 1:
            z = np.polyfit(hop_counts, delays, 1)
            p = np.poly1d(z)
            x_trend = np.linspace(min(hop_counts), max(hop_counts), 100)
            axes[1, 0].plot(x_trend, p(x_trend), '--', color='red', alpha=0.5, label='Trend')
            axes[1, 0].legend()
    
    # Statistics
    path_lengths = [len(p['path']) for p in paths]
    if path_lengths:
        stats_text = f"""
        Total Packets Traced: {len(paths)}
        Average Path Length: {statistics.mean(path_lengths):.2f} nodes
        Min Path Length: {min(path_lengths)} nodes
        Max Path Length: {max(path_lengths)} nodes
        
        Average Hop Count: {statistics.mean(hop_counts) if hop_counts else 0:.2f}
        Min Hops: {min(hop_counts) if hop_counts else 0}
        Max Hops: {max(hop_counts) if hop_counts else 0}
        
        Average Delay: {statistics.mean(delays) if delays else 0:.6f}s
        Min Delay: {min(delays) if delays else 0:.6f}s
        Max Delay: {max(delays) if delays else 0:.6f}s
        """
        axes[1, 1].text(0.1, 0.5, stats_text, fontsize=11, 
                       verticalalignment='center', family='monospace',
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        axes[1, 1].axis('off')
        axes[1, 1].set_title('Packet Tracing Statistics', fontsize=14)
    
    plt.tight_layout()
    plt.savefig("packet_tracing.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("    ✓ Saved: packet_tracing.png")


def plot_protocol_metrics():
    """Plot comprehensive protocol metrics."""
    print("  Generating comprehensive protocol metrics plots...")
    
    metrics = load_all_metrics()
    
    if not metrics:
        print("    Warning: No metrics found")
        return
    
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    fig.suptitle('Comprehensive Protocol Performance Metrics', fontsize=16, fontweight='bold')
    
    # Join time
    ax1 = fig.add_subplot(gs[0, 0])
    if 'join_times' in metrics and metrics['join_times']:
        join_times = metrics['join_times']
        ax1.hist(join_times, bins=30, edgecolor='black', alpha=0.7, color='lightblue')
        ax1.axvline(statistics.mean(join_times), color='red', linestyle='--', 
                   label=f'Mean: {statistics.mean(join_times):.2f}s')
        ax1.set_xlabel('Join Time (s)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Network Join Time Distribution')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
    
    # Packet delay
    ax2 = fig.add_subplot(gs[0, 1])
    if 'packet_delays' in metrics and metrics['packet_delays']:
        delays = metrics['packet_delays']
        ax2.hist(delays, bins=50, edgecolor='black', alpha=0.7, color='lightgreen')
        ax2.axvline(statistics.mean(delays), color='red', linestyle='--',
                   label=f'Mean: {statistics.mean(delays):.6f}s')
        ax2.set_xlabel('Packet Delay (s)')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Packet Delay Distribution')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
    
    # Role changes
    ax3 = fig.add_subplot(gs[0, 2])
    if 'role_changes' in metrics and metrics['role_changes']:
        role_times = []
        for rc in metrics['role_changes']:
            try:
                role_times.append(float(rc['time']))
            except (ValueError, KeyError):
                pass
        if role_times:
            ax3.hist(role_times, bins=30, edgecolor='black', alpha=0.7, color='orange')
            ax3.set_xlabel('Simulation Time (s)')
            ax3.set_ylabel('Number of Role Changes')
            ax3.set_title('Role Changes Over Time')
            ax3.grid(True, alpha=0.3)
    
    # Role transitions
    ax4 = fig.add_subplot(gs[1, 0])
    if 'role_changes' in metrics and metrics['role_changes']:
        transitions = Counter()
        for rc in metrics['role_changes']:
            old_role = rc.get('old_role', '')
            new_role = rc.get('new_role', '')
            if old_role and new_role:
                transitions[f"{old_role}→{new_role}"] += 1
        if transitions:
            roles = list(transitions.keys())
            counts = list(transitions.values())
            ax4.barh(range(len(roles)), counts, alpha=0.7, color='purple', edgecolor='black')
            ax4.set_yticks(range(len(roles)))
            ax4.set_yticklabels(roles)
            ax4.set_xlabel('Count')
            ax4.set_title('Role Transition Frequencies')
            ax4.grid(True, alpha=0.3, axis='x')
    
    # Recovery
    ax5 = fig.add_subplot(gs[1, 1])
    if 'recoveries' in metrics and metrics['recoveries']:
        downtimes = []
        for rec in metrics['recoveries']:
            try:
                downtimes.append(float(rec['downtime']))
            except (ValueError, KeyError):
                pass
        if downtimes:
            ax5.hist(downtimes, bins=20, edgecolor='black', alpha=0.7, color='red')
            ax5.axvline(statistics.mean(downtimes), color='blue', linestyle='--',
                       label=f'Mean: {statistics.mean(downtimes):.2f}s')
            ax5.set_xlabel('Recovery Time (s)')
            ax5.set_ylabel('Frequency')
            ax5.set_title('Node Recovery Time Distribution')
            ax5.legend()
            ax5.grid(True, alpha=0.3)
    else:
        ax5.text(0.5, 0.5, 'No recovery events', ha='center', va='center')
        ax5.set_title('Node Recovery Statistics')
    
    # Clusters
    ax6 = fig.add_subplot(gs[1, 2])
    if 'cluster_heads' in metrics:
        num_clusters = len(metrics['cluster_heads'])
        ax6.bar(['Clusters'], [num_clusters], alpha=0.7, color='steelblue', edgecolor='black')
        ax6.set_ylabel('Number of Clusters')
        ax6.set_title('Cluster Formation')
        ax6.grid(True, alpha=0.3, axis='y')
        ax6.text(0, num_clusters, str(num_clusters), ha='center', va='bottom', fontweight='bold')
    
    # Orphans
    ax7 = fig.add_subplot(gs[2, 0])
    if 'orphans' in metrics and metrics['orphans']:
        orphan_reasons = Counter([o.get('reason', 'Unknown') for o in metrics['orphans']])
        if orphan_reasons:
            reasons = list(orphan_reasons.keys())
            counts = list(orphan_reasons.values())
            ax7.bar(range(len(reasons)), counts, alpha=0.7, color='coral', edgecolor='black')
            ax7.set_xticks(range(len(reasons)))
            ax7.set_xticklabels(reasons, rotation=45, ha='right')
            ax7.set_ylabel('Count')
            ax7.set_title('Orphan Event Reasons')
            ax7.grid(True, alpha=0.3, axis='y')
    
    # Summary
    ax8 = fig.add_subplot(gs[2, 1:])
    stats_text = "PROTOCOL PERFORMANCE SUMMARY\n" + "="*50 + "\n\n"
    
    if 'join_times' in metrics and metrics['join_times']:
        jt = metrics['join_times']
        stats_text += f"Join Time Statistics:\n"
        stats_text += f"  Mean: {statistics.mean(jt):.4f}s\n"
        stats_text += f"  Median: {statistics.median(jt):.4f}s\n"
        stats_text += f"  Min: {min(jt):.4f}s\n"
        stats_text += f"  Max: {max(jt):.4f}s\n"
        stats_text += f"  Std Dev: {statistics.stdev(jt) if len(jt) > 1 else 0:.4f}s\n\n"
    
    if 'packet_delays' in metrics and metrics['packet_delays']:
        pd = metrics['packet_delays']
        stats_text += f"Packet Delay Statistics:\n"
        stats_text += f"  Mean: {statistics.mean(pd):.6f}s\n"
        stats_text += f"  Median: {statistics.median(pd):.6f}s\n"
        stats_text += f"  Total Packets: {len(pd)}\n\n"
    
    if 'cluster_heads' in metrics:
        stats_text += f"Cluster Formation:\n"
        stats_text += f"  Number of Clusters: {len(metrics['cluster_heads'])}\n\n"
    
    if 'role_changes' in metrics:
        stats_text += f"Role Changes: {len(metrics['role_changes'])}\n"
    
    if 'recoveries' in metrics:
        stats_text += f"Recovery Events: {len(metrics['recoveries'])}\n"
    
    if 'orphans' in metrics:
        stats_text += f"Orphan Events: {len(metrics['orphans'])}\n"
    
    ax8.text(0.05, 0.95, stats_text, transform=ax8.transAxes,
            fontsize=10, verticalalignment='top', family='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    ax8.axis('off')
    
    plt.savefig("protocol_metrics.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("    ✓ Saved: protocol_metrics.png")


def plot_config_parameters():
    """Plot configuration parameters analysis."""
    print("  Generating configuration parameters plots...")
    
    params = load_config_parameters()
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Configuration Parameters Analysis', fontsize=16, fontweight='bold')
    
    # Max cluster size vs clusters
    max_sizes = range(5, 51, 5)
    total_nodes = int(params.get('SIM_NODE_COUNT', 100)) if params else 100
    estimated_cluster_counts = [int(np.ceil(total_nodes / s)) for s in max_sizes]
    
    axes[0, 0].plot(max_sizes, estimated_cluster_counts, 'o-', linewidth=2, markersize=8, color='blue')
    if params and 'MAX_CHILD_NODES_ALLOWED_PER_CLUSTER' in params:
        current_max = int(params['MAX_CHILD_NODES_ALLOWED_PER_CLUSTER'])
        current_clusters = int(np.ceil(total_nodes / current_max))
        axes[0, 0].axvline(current_max, color='red', linestyle='--', 
                         label=f'Current: {current_max} (→{current_clusters} clusters)')
        axes[0, 0].plot(current_max, current_clusters, 'ro', markersize=12)
    axes[0, 0].set_xlabel('Max Nodes per Cluster', fontsize=12)
    axes[0, 0].set_ylabel('Estimated Number of Clusters', fontsize=12)
    axes[0, 0].set_title('Cluster Size vs Cluster Count Trade-off', fontsize=14)
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # TX Range
    tx_ranges = range(80, 201, 10)
    coverage_areas = [(r * 2) ** 2 for r in tx_ranges]
    
    axes[0, 1].plot(tx_ranges, coverage_areas, 's-', linewidth=2, markersize=6, color='green')
    if params and 'NODE_TX_RANGE' in params:
        current_tx = int(params['NODE_TX_RANGE'])
        current_coverage = (current_tx * 2) ** 2
        axes[0, 1].axvline(current_tx, color='red', linestyle='--',
                          label=f'Current: {current_tx}m')
        axes[0, 1].plot(current_tx, current_coverage, 'ro', markersize=12)
    axes[0, 1].set_xlabel('TX Range (meters)', fontsize=12)
    axes[0, 1].set_ylabel('Coverage Area (m²)', fontsize=12)
    axes[0, 1].set_title('TX Range vs Coverage Area', fontsize=14)
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    
    # Heartbeat interval
    hb_intervals = range(5, 101, 5)
    discovery_times = [hb * 2 for hb in hb_intervals]
    
    axes[1, 0].plot(hb_intervals, discovery_times, '^-', linewidth=2, markersize=6, color='orange')
    if params and 'HEARTH_BEAT_TIME_INTERVAL' in params:
        current_hb = int(params['HEARTH_BEAT_TIME_INTERVAL'])
        current_discovery = current_hb * 2
        axes[1, 0].axvline(current_hb, color='red', linestyle='--',
                          label=f'Current: {current_hb}s')
        axes[1, 0].plot(current_hb, current_discovery, 'ro', markersize=12)
    axes[1, 0].set_xlabel('Heartbeat Interval (seconds)', fontsize=12)
    axes[1, 0].set_ylabel('Estimated Discovery Time (seconds)', fontsize=12)
    axes[1, 0].set_title('Heartbeat Interval vs Discovery Time', fontsize=14)
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    
    # Config summary
    ax = axes[1, 1]
    if params:
        config_text = "CURRENT CONFIGURATION\n" + "="*30 + "\n\n"
        for key, value in sorted(params.items()):
            display_key = key.replace('_', ' ').title()
            if isinstance(value, float):
                if value < 1:
                    config_text += f"{display_key:35s}: {value:.6f}\n"
                else:
                    config_text += f"{display_key:35s}: {value:.1f}\n"
            else:
                config_text += f"{display_key:35s}: {int(value)}\n"
        
        ax.text(0.1, 0.5, config_text, fontsize=10, 
               verticalalignment='center', family='monospace',
               bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    else:
        ax.text(0.5, 0.5, 'Could not load configuration', 
               ha='center', va='center', fontsize=12)
    ax.axis('off')
    ax.set_title('Configuration Summary', fontsize=14)
    
    plt.tight_layout()
    plt.savefig("config_parameters.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("    ✓ Saved: config_parameters.png")


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function to generate all plots."""
    print("="*70)
    print("GENERATING ALL PLOTS FOR REPORT")
    print("="*70)
    print("\nThis script will generate all analysis plots.")
    print("Make sure you have run the simulation first to generate CSV files.\n")
    
    plots_to_generate = [
        ("Join Time Analysis", plot_join_time_analysis),
        ("Cluster Analysis", plot_cluster_analysis),
        ("TX Power Analysis", plot_tx_power_analysis),
        ("Network Lifetime", plot_network_lifetime),
        ("Packet Tracing", plot_packet_tracing),
        ("Protocol Metrics", plot_protocol_metrics),
        ("Config Parameters", plot_config_parameters),
    ]
    
    results = {}
    
    for name, plot_func in plots_to_generate:
        print(f"\n[{name}]")
        try:
            plot_func()
            results[name] = True
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    successful = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, success in results.items():
        status = "✓" if success else "✗"
        print(f"{status} {name}")
    
    print(f"\nCompleted: {successful}/{total} plots generated")
    
    if successful == total:
        print("\n✓ All plots generated successfully!")
    else:
        print(f"\n⚠ {total - successful} plot(s) failed. Check errors above.")
    
    print("\nGenerated plots:")
    for name in results.keys():
        print(f"  - {name.lower().replace(' ', '_')}.png")
    print("="*70)


if __name__ == "__main__":
    main()
