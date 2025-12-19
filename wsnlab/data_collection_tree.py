import random
from enum import Enum
import sys
import math
import csv
import json
import os
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(1, '.')
from source import wsnlab_vis as wsn
from source import config

DEBUG_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".cursor", "debug.log")

def debug_log(location, message, data, hypothesis_id):
    # Log debug information to file.
    try:
        os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps({
                "location": location,
                "message": message,
                "data": data,
                "timestamp": datetime.now().timestamp(),
                "sessionId": "debug-session",
                "hypothesisId": hypothesis_id
            }) + "\n")
    except Exception:
        pass

NODE_POS = {}

LOG_FILE = None
LOG_FILE_NAME = None
PACKET_ROUTE_FILE = "packet_routes.csv"
PACKET_ROUTE_HEADER_WRITTEN = False
PACKET_DELAY_FILE = "packet_delays.csv"
REGISTRATION_LOG_FILE = "registration_log.csv"
PACKET_PATH_FILE = "packet_paths.csv"
DATA_PACKET_COUNTER = 0

PACKET_STATS = {
    'total_attempts': 0,
    'total_dropped': 0,
    'type_attempts': Counter(),
    'type_dropped': Counter()
}

# --- recovery tracking ---
RECOVERY_LOG_FILE = "recovery_events.csv"
ORPHAN_LOG_FILE = "orphan_events.csv"
ROLE_CHANGE_LOG_FILE = "role_changes.csv"
SNAPSHOT_LOG_FILE = "network_snapshots.csv"
POWER_LOG_FILE = "node_power_levels_over_time.csv"
POWER_LOG_HEADER_WRITTEN = False
FAILED_NODES = set()
ORPHANED_NODES = set()
RECOVERY_EVENTS = []
SCHEDULED_FAILURES = []
SCHEDULED_RECOVERIES = []

# --- connectivity tracking ---
CONNECTIVITY_LOG_FILE = "connectivity_over_time.csv"
CONNECTIVITY_THRESHOLD = 0.80  # 80% connectivity threshold for network lifetime
NETWORK_LIFETIME_REACHED = False
NETWORK_LIFETIME_TIME = None
CONNECTIVITY_CHECK_INTERVAL = 100.0  # Check connectivity every 100 seconds
CONNECTIVITY_CHECK_START_DELAY = 500.0  # Start connectivity checks after 500s (allow network formation)

# --- tracking containers ---
ALL_NODES = []
CLUSTER_HEADS = []
ROLE_COUNTS = Counter()

def _addr_str(a): return "" if a is None else str(a)
def _role_name(r): return r.name if hasattr(r, "name") else str(r)
def addr_key(addr):
    # Return hashable tuple for an address.
    if addr is None:
        return None
    return (getattr(addr, 'net_addr', None), getattr(addr, 'node_addr', None))

def format_addr(addr):
    if addr is None:
        return "None"
    return f"[{addr.net_addr},{addr.node_addr}]"

def addr_equals(a, b):
    # Safe address comparison that tolerates None values.
    if a is None or b is None:
        return False
    try:
        return a == b
    except AttributeError:
        return False

def next_packet_id():
    # Return a monotonically increasing packet identifier.
    global DATA_PACKET_COUNTER
    DATA_PACKET_COUNTER += 1
    return DATA_PACKET_COUNTER

def log_power_level(node_id, time, power):
    global POWER_LOG_HEADER_WRITTEN
    try:
        with open(POWER_LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            if not POWER_LOG_HEADER_WRITTEN:
                writer.writerow(["time", "node_id", "power"])
                POWER_LOG_HEADER_WRITTEN = True
            writer.writerow([time, node_id, power])
    except Exception:
        pass

def init_log_file():
    # Create timestamped log file if enabled.
    global LOG_FILE, LOG_FILE_NAME, PACKET_ROUTE_HEADER_WRITTEN, POWER_LOG_HEADER_WRITTEN
    if not config.ENABLE_LOG_FILE or LOG_FILE is not None:
        return None
    timestamp = datetime.now().strftime("%d-%m-%y-%H%M")
    LOG_FILE_NAME = f"wsn_log_{timestamp}.log"
    LOG_FILE = open(LOG_FILE_NAME, "w", buffering=1)
    print(f"Logging to {LOG_FILE_NAME}")
    LOG_FILE.write(f"Logging to {LOG_FILE_NAME}\n")
    LOG_FILE.flush()

    with open(PACKET_ROUTE_FILE, "w", newline="") as f:
        pass
    with open(PACKET_DELAY_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["packet_type", "source", "dest", "source_gui", "dest_gui",
                         "created_at", "delivered_at", "base_delay", "total_delay",
                         "tx_time", "rx_time", "processing_time", "num_hops"])
    with open(REGISTRATION_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["node_id", "start_time", "registered_time", "join_delay"])
    with open(PACKET_PATH_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["packet_id", "packet_type", "source_gui", "dest_gui",
                         "path", "hop_count", "started_at", "delivered_at", "delay"])

    with open(RECOVERY_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["node_id", "failure_time", "recovery_time", "downtime",
                         "orphan_count_at_recovery", "role_before_failure", "role_after_recovery"])
    with open(ORPHAN_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["node_id", "time", "reason", "parent_id"])
    with open(ROLE_CHANGE_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["node_id", "old_role", "new_role", "time", "reason"])

    with open(SNAPSHOT_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["snapshot_time", "snapshot_label", "node_id", "position_x", "position_y",
                         "role", "is_failed", "is_orphan", "parent_gui", "cluster_id",
                         "num_children", "energy_remaining", "hop_count", "addr", "ch_addr"])
    
    with open(CONNECTIVITY_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "total_nodes", "registered_nodes", "connected_nodes", "connectivity_percentage", 
                         "packets_sent", "packets_delivered", "energy_depleted_nodes"])
    
    PACKET_ROUTE_HEADER_WRITTEN = False
    return LOG_FILE_NAME

def write_log(node_ref, message, sim_time=None):
    # Write structured log to file.
    if not config.ENABLE_LOG_FILE or LOG_FILE is None:
        return
    try:
        node_id = None
        if hasattr(node_ref, 'id'):
            node_id = node_ref.id
            if sim_time is None:
                sim_time = getattr(node_ref, 'now', 0)
        elif isinstance(node_ref, int):
            node_id = node_ref
        else:
            node_id = None
        if sim_time is None and 'sim' in globals():
            sim_time = getattr(sim, 'now', 0)
        if sim_time is None:
            sim_time = 0
        tag = f"N{node_id}" if node_id is not None else "SYS"
        LOG_FILE.write(f"[{sim_time:10.5f}] {tag} {message}\n")
    except Exception:
        pass

def copy_simulation_outputs():
    try:
        routing_strategy = "MT" if config.ENABLE_MESH_ROUTING else "CT"

        packet_loss = getattr(config, 'PACKET_LOSS_RATE', 0)
        node_count = getattr(config, 'SIM_NODE_COUNT', 100)
        mesh_hop = getattr(config, 'MESH_HOP_N', getattr(config, 'MAX_HOP_DISTANCE', 1)) if config.ENABLE_MESH_ROUTING else 0
        num_failures = getattr(config, 'NUM_NODES_TO_FAIL', 0)

        # Base naming: routing, packet loss, node count, mesh hop, failures
        folder_name = f"results_{routing_strategy}_PL{packet_loss}_N{node_count}"
        if config.ENABLE_MESH_ROUTING:
            folder_name += f"_H{mesh_hop}"
        if num_failures > 0:
            folder_name += f"_F{num_failures}"

        # For energy / traffic-load experiments (Fig. 4 style), append energy and traffic
        # so multiple runs with different BATTERY_CAPACITY or DATA_PACKET_INTERVAL
        # do NOT overwrite each other.
        battery_capacity = getattr(config, 'BATTERY_CAPACITY', None)
        data_interval = getattr(config, 'DATA_PACKET_INTERVAL', None)
        try:
            if battery_capacity is not None:
                # Calculate energy in Joules for better folder naming
                battery_voltage = getattr(config, 'BATTERY_VOLTAGE', 3.0)
                energy_joules = battery_capacity * battery_voltage * 3600
                
                # Use Joules for small energy experiments, mAh for large ones
                if energy_joules < 100:  # Use Joules for values under 100J
                    folder_name += f"_E{energy_joules:.1f}J"
                else:
                    folder_name += f"_E{int(battery_capacity)}mAh"
        except Exception:
            pass
        try:
            if data_interval is not None:
                folder_name += f"_TI{int(data_interval)}s"
        except Exception:
            pass

        results_dir = Path(folder_name)
        results_dir.mkdir(exist_ok=True)

        files_to_copy = [
            "registration_log.csv",
            "packet_log.csv",
            "packet_delays.csv",
            "packet_paths.csv",
            "packet_routes.csv",
            "node_power_levels.csv",
            "node_power_levels_over_time.csv",
            "connectivity_over_time.csv",
            "topology.csv",
            "recovery_time.csv",
            "recovery_events.csv",
            "orphan_events.csv",
            "role_changes.csv",
            "network_snapshots.csv",
            "clusterhead_distances.csv",
            "neighbor_distances.csv",
            "multihop_neighbor_table.csv",
            "cluster_members.csv",
            "node_distances.csv",
            "node_distance_matrix.csv",
            # Power analysis CSV files (friend's style)
            "averagePower_by_time.csv",
            "NodePower_levels.csv",
            "nodePower_over_time.csv",
            LOG_FILE_NAME if LOG_FILE_NAME else None,
            "wsnlab/source/config.py",
        ]

        copied_count = 0
        for file_path in files_to_copy:
            if file_path is None:
                continue
            src = Path(file_path)
            if src.exists():
                dst = results_dir / src.name
                shutil.copy2(src, dst)
                copied_count += 1

        snapshot_folder = Path(getattr(config, 'SNAPSHOT_FOLDER', 'snapshots'))
        if snapshot_folder.exists() and snapshot_folder.is_dir():
            dst_snapshot = results_dir / snapshot_folder.name
            if dst_snapshot.exists():
                shutil.rmtree(dst_snapshot)
            shutil.copytree(snapshot_folder, dst_snapshot)
            copied_count += 1

        # Calculate initial energy from battery configuration
        battery_capacity = getattr(config, 'BATTERY_CAPACITY', 2000)
        battery_voltage = getattr(config, 'BATTERY_VOLTAGE', 3.0)
        initial_energy = battery_voltage * battery_capacity * 3600  # Joules
        
        metadata = {
            "routing_strategy": routing_strategy,
            "packet_loss_rate": packet_loss,
            "node_count": node_count,
            "mesh_enabled": config.ENABLE_MESH_ROUTING,
            "tree_enabled": config.ENABLE_TREE_ROUTING,
            "mesh_hop_n": mesh_hop if config.ENABLE_MESH_ROUTING else None,
            "num_nodes_to_fail": getattr(config, 'NUM_NODES_TO_FAIL', 0),
            "simulation_duration": getattr(config, 'SIM_DURATION', 5000),
            "initial_energy": initial_energy,  # Add initial energy to metadata
            "battery_capacity": battery_capacity,  # Add battery capacity
            "battery_voltage": battery_voltage,  # Add battery voltage
            "data_packet_interval": getattr(config, 'DATA_PACKET_INTERVAL', 10),  # Add traffic load
            "timestamp": datetime.now().isoformat(),
        }

        metadata_file = results_dir / "simulation_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        log_to_console_and_file(f"📁 Copied {copied_count} files to {folder_name}/")

    except Exception as e:
        log_to_console_and_file(f"⚠️  Error copying simulation outputs: {e}")

def close_log_file():
    global LOG_FILE
    if LOG_FILE is not None:
        LOG_FILE.close()
        LOG_FILE = None

def log_packet_route(pck, current_node, next_hop_str, path_label):
    # Append routing trace rows to packet_routes.csv.
    global PACKET_ROUTE_HEADER_WRITTEN
    try:
        with open(PACKET_ROUTE_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            if not PACKET_ROUTE_HEADER_WRITTEN:
                writer.writerow(["time", "packet_type", "source", "current_node",
                                 "next_hop", "dest", "hop_count", "path_type"])
                PACKET_ROUTE_HEADER_WRITTEN = True
            writer.writerow([
                getattr(current_node, "now", 0),
                pck.get("type"),
                format_addr(pck.get("source")),
                current_node.id,
                next_hop_str,
                format_addr(pck.get("dest")),
                pck.get("hop_count"),
                path_label
            ])
    except Exception:
        pass

def log_packet_delivery(pck, receiver_node):
    try:
        created = pck.get("created_at")
        if created is None:
            return
        delivered = getattr(receiver_node, "now", None)
        if delivered is None:
            return

        base_delay = delivered - created

        packet_size = estimate_packet_size(pck)
        packet_type = pck.get("type", "UNKNOWN")

        tx_time = calculate_transmission_time(packet_size)

        rx_time = calculate_reception_time(packet_size)

        route_trace = pck.get('route_trace', [])
        num_hops = len(route_trace) if route_trace else 1
        processing_time = calculate_processing_time(packet_type) * num_hops

        total_delay = base_delay + tx_time + rx_time + processing_time
        with open(PACKET_DELAY_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                pck.get("type"),
                format_addr(pck.get("source")),
                format_addr(pck.get("dest")),
                pck.get("gui"),
                receiver_node.id,
                f"{created:.6f}",
                f"{delivered:.6f}",
                f"{base_delay:.6f}",
                f"{total_delay:.6f}",
                f"{tx_time:.6f}",
                f"{rx_time:.6f}",
                f"{processing_time:.6f}",
                num_hops,
            ])
    except Exception:
        pass

def record_packet_path(pck, receiver_node):
    # Persist full path for traced data packets.
    if pck.get('type') != 'SENSOR_DATA':
        return
    try:
        created = pck.get('created_at')
        delivered = getattr(receiver_node, "now", None)
        if created is None or delivered is None:
            return
        route = list(pck.get('route_trace', []))
        if not route or route[-1] != receiver_node.id:
            route.append(receiver_node.id)
        hop_count = max(0, len(route) - 1)
        with open(PACKET_PATH_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                pck.get('packet_id'),
                pck.get('type'),
                pck.get('source_gui'),
                pck.get('dest_gui'),
                "->".join(map(str, route)),
                hop_count,
                f"{created:.6f}",
                f"{delivered:.6f}",
                f"{(delivered-created):.6f}"
            ])
    except Exception:
        pass

def log_registration_time(node_id, wake_time, registered_time):
    # Persist per-node join delays.
    if wake_time is None or registered_time is None:
        return
    delay = registered_time - wake_time
    with open(REGISTRATION_LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([node_id, f"{wake_time:.6f}", f"{registered_time:.6f}", f"{delay:.6f}"])

def calculate_and_log_average_packet_delay():
    try:
        base_delays = []
        total_delays = []
        with open(PACKET_DELAY_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "total_delay" in row:
                    base_delays.append(float(row.get("base_delay", 0)))
                    total_delays.append(float(row["total_delay"]))
                elif "delay" in row:
                    delay = float(row["delay"])
                    base_delays.append(delay)
                    total_delays.append(delay)

        if not total_delays:
            print("⚠️ No packet delays recorded.")
            return

        avg_base_delay = sum(base_delays) / len(base_delays)
        avg_total_delay = sum(total_delays) / len(total_delays)
        log_to_console_and_file(f"📦 Average packet delay (base): {avg_base_delay:.6f}s (samples={len(base_delays)})")
        log_to_console_and_file(f"📦 Average packet delay (total, with tx/rx/processing): {avg_total_delay:.6f}s (samples={len(total_delays)})")
        log_to_console_and_file(f"   └─ Difference (tx/rx/processing overhead): {avg_total_delay - avg_base_delay:.6f}s")
    except FileNotFoundError:
        log_to_console_and_file("⚠️ Packet delay log not found.")

def calculate_and_log_average_join_time():
    # Summarize node join time statistics.
    try:
        joins = []
        with open(REGISTRATION_LOG_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                joins.append(float(row["join_delay"]))
        if not joins:
            log_to_console_and_file("⚠️ No registration data recorded.")
            return
        avg_join = sum(joins) / len(joins)
        log_to_console_and_file(f"👥 Average join time: {avg_join:.6f}s (nodes={len(joins)})")
    except FileNotFoundError:
        log_to_console_and_file("⚠️ Registration log not found.")

def log_orphan_event(node_id, time, reason, parent_id=None):
    # Log when a node becomes orphaned.
    try:
        with open(ORPHAN_LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([node_id, f"{time:.6f}", reason, parent_id if parent_id else ""])
        ORPHANED_NODES.add(node_id)
    except Exception:
        pass

def log_role_change(node_id, old_role, new_role, time, reason=""):
    # Log when a node changes roles.
    try:
        with open(ROLE_CHANGE_LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([node_id, _role_name(old_role), _role_name(new_role), f"{time:.6f}", reason])
    except Exception:
        pass

def log_recovery_event(node_id, failure_time, recovery_time, orphan_count, role_before, role_after):
    # Log when a failed node recovers.
    try:
        downtime = recovery_time - failure_time
        with open(RECOVERY_LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([node_id, f"{failure_time:.6f}", f"{recovery_time:.6f}",
                           f"{downtime:.6f}", orphan_count, _role_name(role_before), _role_name(role_after)])
        RECOVERY_EVENTS.append({
            'node_id': node_id,
            'failure_time': failure_time,
            'recovery_time': recovery_time,
            'downtime': downtime,
            'orphan_count': orphan_count
        })
    except Exception:
        pass

def log_to_console_and_file(message):
    # Write message to both console and log file.
    print(message)
    if config.ENABLE_LOG_FILE and LOG_FILE is not None:
        try:
            LOG_FILE.write(message + "\n")
            LOG_FILE.flush()
        except Exception:
            pass

def take_network_snapshot(snapshot_label="", sim_time=None):
    try:
        if sim_time is None:
            if ALL_NODES and hasattr(ALL_NODES[0], 'now'):
                sim_time = ALL_NODES[0].now
            elif 'sim' in globals() and hasattr(globals()['sim'], 'now'):
                sim_time = globals()['sim'].now
            else:
                sim_time = 0

        if not snapshot_label:
            snapshot_label = f"Snapshot_{sim_time:.2f}"

        log_to_console_and_file(f"📸 Taking network snapshot: {snapshot_label} at time {sim_time:.2f}s")

        debug_log(f"data_collection_tree.py:{394}", "Snapshot start", {"snapshot_label": snapshot_label, "sim_time": sim_time, "FAILED_NODES": list(FAILED_NODES), "ORPHANED_NODES": list(ORPHANED_NODES)}, "D")

        role_counts = Counter()
        failed_count = 0
        orphan_count = 0
        total_energy = 0

        with open(SNAPSHOT_LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)

            for node in ALL_NODES:
                node_id = node.id
                role = getattr(node, 'role', Roles.UNDISCOVERED)
                role_name = _role_name(role)
                role_counts[role_name] += 1

                pos = NODE_POS.get(node_id, (None, None))
                pos_x, pos_y = pos if pos[0] is not None else (None, None)

                is_failed = getattr(node, 'is_failed', False)
                is_failed_in_set = node_id in FAILED_NODES
                if is_failed:
                    failed_count += 1

                if snapshot_label == "At_T1_Failure" and (is_failed or is_failed_in_set):
                    debug_log(f"data_collection_tree.py:{417}", "Node in snapshot - failed status", {"node_id": node_id, "is_failed_attr": is_failed, "is_failed_in_set": is_failed_in_set, "snapshot_label": snapshot_label}, "D")

                is_orphan = node_id in ORPHANED_NODES
                if is_orphan:
                    orphan_count += 1

                parent_gui = getattr(node, 'parent_gui', None)

                ch_addr = getattr(node, 'ch_addr', None)
                cluster_id = ch_addr.net_addr if ch_addr is not None else None

                members_table = getattr(node, 'members_table', [])
                num_children = len(members_table) if members_table else 0

                energy = getattr(node, 'energy_remaining', None)
                if energy is not None:
                    total_energy += energy

                hop_count = getattr(node, 'hop_count', None)

                addr = getattr(node, 'addr', None)
                addr_str = format_addr(addr) if addr is not None else ""
                ch_addr_str = format_addr(ch_addr) if ch_addr is not None else ""

                writer.writerow([
                    f"{sim_time:.6f}",
                    snapshot_label,
                    node_id,
                    pos_x if pos_x is not None else "",
                    pos_y if pos_y is not None else "",
                    role_name,
                    "YES" if is_failed else "NO",
                    "YES" if is_orphan else "NO",
                    parent_gui if parent_gui is not None else "",
                    cluster_id if cluster_id is not None else "",
                    num_children,
                    f"{energy:.6f}" if energy is not None else "",
                    hop_count if hop_count != 99999 else "",
                    addr_str,
                    ch_addr_str
                ])

        log_to_console_and_file(f"   📊 Snapshot Summary:")
        log_to_console_and_file(f"      Total nodes: {len(ALL_NODES)}")
        log_to_console_and_file(f"      Role distribution: {dict(role_counts)}")
        log_to_console_and_file(f"      Failed nodes: {failed_count}")
        log_to_console_and_file(f"      Orphan nodes: {orphan_count}")
        if total_energy > 0:
            log_to_console_and_file(f"      Total system energy: {total_energy:.2f} J")

        if config.ENABLE_NETWORK_SNAPSHOTS:
            try:
                if config.CAPTURE_SIMULATION_WINDOW and 'sim' in globals():
                    try:
                        from source.wsnlab_vis import capture_simulation_window
                        capture_simulation_window(globals()['sim'], snapshot_label, sim_time, log_to_console_and_file, config)
                    except Exception as sim_capture_error:
                        log_to_console_and_file(f"⚠️  Could not capture simulation window: {sim_capture_error}")
                        from source.wsnlab_vis import save_snapshot_png
                        save_snapshot_png(snapshot_label, sim_time, ALL_NODES, NODE_POS, ORPHANED_NODES, FAILED_NODES,
                                        _role_name, config, log_to_console_and_file)
                else:
                    from source.wsnlab_vis import save_snapshot_png
                    save_snapshot_png(snapshot_label, sim_time, ALL_NODES, NODE_POS, ORPHANED_NODES, FAILED_NODES,
                                    _role_name, config, log_to_console_and_file)
            except Exception as img_error:
                log_to_console_and_file(f"⚠️  Error generating PNG image: {img_error}")

    except Exception as e:
        log_to_console_and_file(f"⚠️  Error taking snapshot: {e}")
        import traceback
        traceback.print_exc()

def check_and_log_connectivity(sim_time=None):
    """
    Check network connectivity (% of nodes connected to sink) and log it.
    Returns True if connectivity drops below threshold (network lifetime reached).
    """
    global NETWORK_LIFETIME_REACHED, NETWORK_LIFETIME_TIME
    
    if NETWORK_LIFETIME_REACHED:
        return True  # Already reached, don't check again
    
    try:
        if sim_time is None:
            if ALL_NODES and hasattr(ALL_NODES[0], 'now'):
                sim_time = ALL_NODES[0].now
            else:
                sim_time = 0
        
        # Find the root/sink node
        root_node = next((n for n in ALL_NODES if n.id == ROOT_ID), None)
        if not root_node:
            return False
        
        total_nodes = len(ALL_NODES)
        if total_nodes == 0:
            return False
        
        # Count registered nodes and connected nodes
        # Only nodes that have joined the network should be counted in the baseline
        # A node is "registered" if it has joined (has a role beyond UNDISCOVERED/UNREGISTERED)
        # A node is "connected" if it's registered AND still alive with energy
        registered_count = 0
        connected_count = 0
        energy_depleted_count = 0
        
        for node in ALL_NODES:
            has_role = hasattr(node, 'role') and node.role not in (Roles.UNDISCOVERED, Roles.UNREGISTERED)
            
            if has_role:
                registered_count += 1  # This node has joined the network
                
                is_alive = not getattr(node, 'is_shutdown', False) and not getattr(node, 'is_failed', False)
                has_energy = getattr(node, 'energy_remaining', 0) > 0
                
                if not has_energy:
                    energy_depleted_count += 1
                
                # Node is connected if it's registered, alive, and has energy
                if is_alive and has_energy:
                    connected_count += 1
        
        # Calculate connectivity as: connected / registered (not connected / total)
        # This way, if 80 nodes joined and 65 are connected, that's 65/80 = 81.25%
        # If we used total (100), it would be 65/100 = 65% and trigger premature lifetime
        if registered_count == 0:
            return False  # No nodes have joined yet, skip check
        
        connectivity_percentage = (connected_count / registered_count) * 100.0
        
        # Get packet statistics
        packets_sent = PACKET_STATS.get('total_attempts', 0)
        packets_delivered = packets_sent - PACKET_STATS.get('total_dropped', 0)
        
        # Log connectivity
        try:
            with open(CONNECTIVITY_LOG_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    f"{sim_time:.2f}",
                    total_nodes,
                    registered_count,
                    connected_count,
                    f"{connectivity_percentage:.2f}",
                    packets_sent,
                    packets_delivered,
                    energy_depleted_count
                ])
        except Exception:
            pass
        
        # Check if network lifetime threshold is reached
        # Use registered_count as baseline (not total_nodes)
        connectivity_ratio = connected_count / registered_count
        if connectivity_ratio < CONNECTIVITY_THRESHOLD and not NETWORK_LIFETIME_REACHED:
            NETWORK_LIFETIME_REACHED = True
            NETWORK_LIFETIME_TIME = sim_time
            
            log_to_console_and_file(f"\n{'='*70}")
            log_to_console_and_file(f"🔴 NETWORK LIFETIME REACHED at t={sim_time:.2f}s")
            log_to_console_and_file(f"   Connectivity: {connectivity_percentage:.1f}% ({connected_count}/{registered_count} registered nodes)")
            log_to_console_and_file(f"   Total nodes: {total_nodes}, Registered: {registered_count}, Unregistered: {total_nodes - registered_count}")
            log_to_console_and_file(f"   Energy depleted: {energy_depleted_count} nodes")
            log_to_console_and_file(f"   Packets sent: {packets_sent}")
            log_to_console_and_file(f"   Packets delivered: {packets_delivered}")
            log_to_console_and_file(f"   Packet delivery ratio: {(packets_delivered/packets_sent*100) if packets_sent > 0 else 0:.2f}%")
            log_to_console_and_file(f"{'='*70}\n")
            
            return True
        
        # Periodic logging (every 10 checks = every 1000s if interval is 100s)
        if config.ENABLE_ENERGY_DEBUG and int(sim_time / CONNECTIVITY_CHECK_INTERVAL) % 10 == 0:
            log_to_console_and_file(f"[CONNECTIVITY] t={sim_time:.0f}s: {connectivity_percentage:.1f}% ({connected_count}/{registered_count} registered), Energy depleted: {energy_depleted_count}, Pkts: {packets_sent}/{packets_delivered}")
        
        return False
        
    except Exception as e:
        log_to_console_and_file(f"⚠️  Error checking connectivity: {e}")
        return False

def calculate_and_log_recovery_statistics():
    # Generate recovery statistics report.
    log_to_console_and_file("")
    log_to_console_and_file("="*70)
    log_to_console_and_file("🔧 NETWORK RECOVERY STATISTICS")
    log_to_console_and_file("="*70)

    try:
        with open(RECOVERY_LOG_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            recoveries = list(reader)

        if recoveries:
            downtimes = [float(r['downtime']) for r in recoveries]
            orphan_counts = [int(r['orphan_count_at_recovery']) for r in recoveries]

            log_to_console_and_file(f"\n📊 Node Failures & Recoveries: {len(recoveries)} events")
            log_to_console_and_file(f"   Average recovery time: {sum(downtimes)/len(downtimes):.2f}s")
            log_to_console_and_file(f"   Min recovery time: {min(downtimes):.2f}s")
            log_to_console_and_file(f"   Max recovery time: {max(downtimes):.2f}s")
            log_to_console_and_file(f"   Total orphan nodes created: {sum(orphan_counts)}")

            log_to_console_and_file(f"\n📋 Recovery Details:")
            for r in recoveries:
                log_to_console_and_file(f"   Node {r['node_id']}: Failed at {float(r['failure_time']):.1f}s, "
                      f"Recovered at {float(r['recovery_time']):.1f}s, "
                      f"Downtime: {float(r['downtime']):.1f}s, "
                      f"Orphans: {r['orphan_count_at_recovery']}")
        else:
            log_to_console_and_file("\n⚠️  No node failures occurred during simulation")

        with open(ORPHAN_LOG_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            orphans = list(reader)

        if orphans:
            log_to_console_and_file(f"\n👥 Orphan Events: {len(orphans)} total")
            orphan_reasons = Counter([o['reason'] for o in orphans])
            for reason, count in orphan_reasons.most_common():
                log_to_console_and_file(f"   {reason}: {count} nodes")

        with open(ROLE_CHANGE_LOG_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            role_changes = list(reader)

        if role_changes:
            log_to_console_and_file(f"\n🔄 Role Changes: {len(role_changes)} total")
            for rc in role_changes[:10]:
                log_to_console_and_file(f"   Node {rc['node_id']}: {rc['old_role']} → {rc['new_role']} "
                      f"at {float(rc['time']):.1f}s ({rc['reason']})")
            if len(role_changes) > 10:
                log_to_console_and_file(f"   ... and {len(role_changes)-10} more role changes")

    except FileNotFoundError as e:
        log_to_console_and_file(f"\n⚠️  Recovery logs not found: {e}")
    except Exception as e:
        log_to_console_and_file(f"\n⚠️  Error generating recovery statistics: {e}")

    log_to_console_and_file("="*70)

def log_packet_loss_statistics():
    # Summarize packet loss counters.
    total = PACKET_STATS['total_attempts']
    dropped = PACKET_STATS['total_dropped']
    if total == 0:
        log_to_console_and_file("\n📡 Packet Loss Stats: No packets attempted.")
        return

    delivered = total - dropped
    loss_pct = (dropped / total) * 100

    log_to_console_and_file("\n📡 Packet Loss Statistics")
    log_to_console_and_file(f"   Attempts : {total}")
    log_to_console_and_file(f"   Delivered: {delivered}")
    log_to_console_and_file(f"   Dropped  : {dropped} ({loss_pct:.2f}%)")

    if PACKET_STATS['type_attempts']:
        log_to_console_and_file("   Breakdown by packet type:")
        for p_type, attempts in PACKET_STATS['type_attempts'].most_common():
            type_drops = PACKET_STATS['type_dropped'].get(p_type, 0)
            type_loss = (type_drops / attempts) * 100 if attempts else 0.0
            log_to_console_and_file(
                f"      {p_type}: attempts={attempts}, dropped={type_drops} ({type_loss:.2f}%)"
            )

def get_tx_current(tx_power_dbm):
    if tx_power_dbm not in config.TX_POWER_LEVELS:
        sorted_powers = sorted(config.TX_POWER_LEVELS.keys())
        if tx_power_dbm < sorted_powers[0]:
            tx_power_dbm = sorted_powers[0]
        elif tx_power_dbm > sorted_powers[-1]:
            tx_power_dbm = sorted_powers[-1]
        else:
            for i in range(len(sorted_powers) - 1):
                if sorted_powers[i] <= tx_power_dbm <= sorted_powers[i + 1]:
                    p1, p2 = sorted_powers[i], sorted_powers[i + 1]
                    i1, i2 = config.TX_POWER_LEVELS[p1], config.TX_POWER_LEVELS[p2]
                    ratio = (tx_power_dbm - p1) / (p2 - p1)
                    current_ma = i1 + ratio * (i2 - i1)
                    return current_ma / 1000.0

    current_ma = config.TX_POWER_LEVELS[tx_power_dbm]
    return current_ma / 1000.0

def calculate_tx_energy(packet_size_bytes, tx_power_dbm=0, include_pll_overhead=True):
    if not config.ENABLE_ENERGY_MODEL:
        return 0.0

    i_tx = get_tx_current(tx_power_dbm)

    total_bytes = packet_size_bytes + config.CC2420_PHY_OVERHEAD
    total_bits = total_bytes * 8
    transmission_time = total_bits / config.CC2420_DATA_RATE
    tx_energy = config.CC2420_VOLTAGE * i_tx * transmission_time

    if include_pll_overhead:
        tx_energy += config.CC2420_PLL_OVERHEAD_ENERGY

    return tx_energy

def calculate_rx_energy(packet_size_bytes, include_pll_overhead=True):
    if not config.ENABLE_ENERGY_MODEL:
        return 0.0

    i_rx = config.CC2420_RX_CURRENT / 1000.0

    total_bytes = packet_size_bytes + config.CC2420_PHY_OVERHEAD
    total_bits = total_bytes * 8
    reception_time = total_bits / config.CC2420_DATA_RATE
    rx_energy = config.CC2420_VOLTAGE * i_rx * reception_time

    if include_pll_overhead:
        rx_energy += config.CC2420_PLL_OVERHEAD_ENERGY

    return rx_energy

def calculate_transmission_time(packet_size_bytes):
    total_bytes = packet_size_bytes + config.CC2420_PHY_OVERHEAD
    total_bits = total_bytes * 8
    transmission_time = total_bits / config.CC2420_DATA_RATE
    return transmission_time

def calculate_reception_time(packet_size_bytes):
    total_bytes = packet_size_bytes + config.CC2420_PHY_OVERHEAD
    total_bits = total_bytes * 8
    reception_time = total_bits / config.CC2420_DATA_RATE
    return reception_time

def calculate_processing_time(packet_type):
    processing_times = {
        'HEART_BEAT': 0.0001,
        'JOIN_REQUEST': 0.0002,
        'JOIN_REPLY': 0.0002,
        'JOIN_ACK': 0.0001,
        'NETWORK_REQUEST': 0.0002,
        'NETWORK_REPLY': 0.0003,
        'NETWORK_UPDATE': 0.0003,
        'NEIGHBOR_SHARE': 0.0002,
        'PROBE': 0.0001,
        'SENSOR_DATA': 0.0002,
    }
    return processing_times.get(packet_type, 0.0002)

def estimate_packet_size(packet):
    base_overhead = 10

    packet_type = packet.get('type', 'UNKNOWN')
    if packet_type == 'HEART_BEAT':
        return 20 + base_overhead
    elif packet_type == 'JOIN_REQUEST':
        return 10 + base_overhead
    elif packet_type == 'JOIN_REPLY':
        return 15 + base_overhead
    elif packet_type == 'JOIN_ACK':
        return 10 + base_overhead
    elif packet_type == 'NETWORK_REQUEST':
        return 10 + base_overhead
    elif packet_type == 'NETWORK_REPLY':
        return 15 + base_overhead
    elif packet_type in ('SENSOR', 'SENSOR_DATA'):
        return 50 + base_overhead
    elif packet_type == 'NEIGHBOR_SHARE':
        neighbors_info = packet.get('neighbors_info', {})
        return 20 + len(neighbors_info) * 10 + base_overhead
    else:
        return 30 + base_overhead

CLUSTER_TX_POWER = {}

def get_cluster_tx_power(cluster_id):
    if config.USE_GLOBAL_TX_POWER:
        return config.TX_POWER_DEFAULT

    if cluster_id in CLUSTER_TX_POWER:
        return CLUSTER_TX_POWER[cluster_id]

    return config.TX_POWER_DEFAULT

def set_cluster_tx_power(cluster_id, tx_power_dbm):
    tx_power_dbm = max(config.TX_POWER_MIN, min(config.TX_POWER_MAX, tx_power_dbm))
    CLUSTER_TX_POWER[cluster_id] = tx_power_dbm

    if config.ENABLE_ENERGY_DEBUG:
        log_to_console_and_file(f"[ENERGY] Cluster {cluster_id} TX power set to {tx_power_dbm} dBm")

def optimize_clusters():
    if not config.ENABLE_CLUSTER_OPTIMIZATION:
        return

    active_chs = [node for node in ALL_NODES
                  if node.role == Roles.CLUSTER_HEAD and not node.is_shutdown and node.ch_addr is not None]
    if len(active_chs) <= 1:
        return

    if config.CLUSTER_OPTIMIZATION_MODE == 'CLUSTERS':
        if config.ENABLE_ENERGY_DEBUG:
            log_to_console_and_file(f"[CLUSTER_OPT] Running cluster minimization (current: {len(active_chs)} clusters)")
    elif config.CLUSTER_OPTIMIZATION_MODE == 'ENERGY':
        if config.ENABLE_ENERGY_DEBUG:
            log_to_console_and_file(f"[CLUSTER_OPT] Running energy optimization (current: {len(active_chs)} clusters)")

        for ch in active_chs:
            cluster_id = ch.ch_addr.net_addr
            member_count = len(ch.members_table)

            if member_count <= 3:
                optimal_power = max(config.TX_POWER_MIN, config.TX_POWER_DEFAULT - 10)
            elif member_count <= 10:
                optimal_power = config.TX_POWER_DEFAULT - 5
            else:
                optimal_power = config.TX_POWER_DEFAULT

            current_power = get_cluster_tx_power(cluster_id)
            if abs(current_power - optimal_power) > 1.0:
                set_cluster_tx_power(cluster_id, optimal_power)

                for node in ALL_NODES:
                    if node.ch_addr is not None and node.ch_addr.net_addr == cluster_id:
                        node.update_cluster_tx_power()

                if config.ENABLE_ENERGY_DEBUG:
                    log_to_console_and_file(f"[CLUSTER_OPT] Cluster {cluster_id}: TX power optimized from {current_power} to {optimal_power} dBm (members={member_count})")
Roles = Enum('Roles', 'UNDISCOVERED UNREGISTERED ROOT REGISTERED CLUSTER_HEAD ROUTER')
"""Enumeration of roles"""

class SensorNode(wsn.Node):

    def init(self):
        self.scene.nodecolor(self.id, 1, 1, 1)
        self.sleep()
        self.addr = None
        self.ch_addr = None
        self.parent_gui = None
        self.root_addr = None
        self.wake_up_time = None
        self.registered_time = None
        self.tx_range_circle_id = None
        self.set_role(Roles.UNDISCOVERED)
        self.is_root_eligible = True if self.id == ROOT_ID else False
        self.c_probe = 0
        self.th_probe = 10
        self.hop_count = 99999
        self.neighbors_table = {}
        self.candidate_parents_table = []
        self.child_networks_table = {}
        self.members_table = []
        self.received_JR_guis = []

        self.node_addr_pool = {}
        self.cluster_addr_pool = {}

        self.energy_remaining = config.BATTERY_ENERGY_TOTAL
        self.energy_initial = config.BATTERY_ENERGY_TOTAL
        self.energy_tx_total = 0.0
        self.energy_rx_total = 0.0
        self.energy_baseline_total = 0.0
        self.is_shutdown = False
        self.shutdown_time = None

        self.tx_power_dbm = config.TX_POWER_DEFAULT
        self.cluster_tx_power_dbm = None

        if config.ENABLE_ENERGY_MODEL and config.ENABLE_ENERGY_DEBUG:
            msg = f"[ENERGY] Node {self.id}: Initialized with {self.energy_remaining:.6f}J ({config.BATTERY_ENERGY_TOTAL:.6f}J total, TX power={self.tx_power_dbm}dBm)"
            self.log(msg)
            write_log(self, msg)

        self.multihop_neighbor_table = {}

        self.is_failed = False
        self.failure_time = None
        self.role_before_failure = None
        self.children_before_failure = []

        self.ch_transfer_enabled = getattr(config, 'ENABLE_CH_TRANSFER', True)
        self.ch_transfer_in_progress = False
        self.ch_transfer_candidate = None

        self.failed_join_attempts = 0
        self.registered_since = None

        self.join_reply_last_sent = {}
        self.join_reply_cooldown = 5.0

        self.last_join_request_sent_time = None
        self.join_request_cooldown = 20

        self.last_trigger_ch_creation_time = None
        self.trigger_ch_creation_cooldown = 60.0

        self.heartbeat_timer_active = False

        self.last_network_update_sent_time = None
        self.network_update_cooldown = 5.0
        self.last_child_networks_sent = None

    def run(self):
        self.set_timer('TIMER_ARRIVAL', self.arrival)

    def debug_log(self, enabled, message):
        # Log to console and file when enabled.
        if enabled:
            self.log(message)
            write_log(self, message)

    def set_role(self, new_role, *, recolor=True, reason=""):
        # Central place to switch roles, keep tallies, and (optionally) recolor.
        old_role = getattr(self, "role", None)

        if new_role == Roles.CLUSTER_HEAD and self.ch_addr is not None:
            cluster_id = self.ch_addr.net_addr
            existing_ch, existing_ch_gui = self._check_existing_ch_in_cluster(cluster_id)
            if existing_ch and existing_ch_gui != self.id:
                existing_ch_node = self._find_node_by_gui(existing_ch_gui)
                if existing_ch_node:
                    existing_members = len(existing_ch_node.members_table) if hasattr(existing_ch_node, 'members_table') else 0
                    my_members = len(self.members_table) if hasattr(self, 'members_table') else 0

                    if existing_members > my_members or (existing_members == my_members and existing_ch_gui < self.id):
                        write_log(self, f"[CH_DUPLICATE] Node {self.id}: CH {existing_ch_gui} already exists with cluster {cluster_id} (members: {existing_members} vs {my_members}), becoming router instead")
                        self.ch_addr = None
                        self.set_role(Roles.ROUTER, reason=f"Duplicate CH detected - existing CH {existing_ch_gui} has cluster {cluster_id}")
                        return

        if old_role is not None:
            ROLE_COUNTS[old_role] -= 1
            if ROLE_COUNTS[old_role] <= 0:
                ROLE_COUNTS.pop(old_role, None)
        ROLE_COUNTS[new_role] += 1
        self.role = new_role

        if old_role is not None and old_role != new_role:
            log_role_change(self.id, old_role, new_role, self.sim.now, reason)

        if recolor:
            if new_role == Roles.UNDISCOVERED:
                self.scene.nodecolor(self.id, 1, 1, 1)
            elif new_role == Roles.UNREGISTERED:
                self.scene.nodecolor(self.id, 1, 1, 0)
            elif new_role == Roles.REGISTERED:
                self.scene.nodecolor(self.id, 0, 1, 0)
            elif new_role == Roles.CLUSTER_HEAD:
                self.scene.nodecolor(self.id, 0, 0, 1)
                self.draw_tx_range()
                if config.ENABLE_ENERGY_MODEL:
                    self.set_timer('TIMER_POWER_LOG', 100.0)
            elif new_role == Roles.ROOT:
                self.scene.nodecolor(self.id, 0, 0, 0)
                self.draw_tx_range()
                self.set_timer('TIMER_EXPORT_CH_CSV', config.EXPORT_CH_CSV_INTERVAL)
                self.set_timer('TIMER_EXPORT_NEIGHBOR_CSV', config.EXPORT_NEIGHBOR_CSV_INTERVAL)
                # Periodic snapshots for energy experiments (to track connectivity over time)
                if config.ENABLE_NETWORK_SNAPSHOTS and getattr(config, 'SNAPSHOT_PERIODIC_ENABLED', False):
                    interval = getattr(config, 'SNAPSHOT_PERIODIC_INTERVAL', 100)
                    self.set_timer('TIMER_PERIODIC_SNAPSHOT', interval)
                # Periodic connectivity check for network lifetime tracking
                # Start after delay to allow network formation
                if config.ENABLE_ENERGY_MODEL:
                    self.set_timer('TIMER_CONNECTIVITY_CHECK', CONNECTIVITY_CHECK_START_DELAY)
                if config.ENABLE_ENERGY_MODEL:
                    self.set_timer('TIMER_POWER_LOG', 100.0)
            elif new_role == Roles.ROUTER:
                self.scene.nodecolor(self.id, 1, 0, 0.75)
                if hasattr(self, 'tx_range_circle_id') and self.tx_range_circle_id is not None:
                    try:
                        self.scene.delshape(self.tx_range_circle_id)
                        self.tx_range_circle_id = None
                    except Exception:
                        pass
                if config.ENABLE_ENERGY_MODEL:
                    self.set_timer('TIMER_POWER_LOG', 100.0)

    def become_router(self, reason="CH role transferred"):
        if self.role != Roles.CLUSTER_HEAD or self.id == ROOT_ID:
            return

        prev_ch_addr = self.ch_addr

        orphan_count = 0

        for child_addr in list(self.members_table):
            child_node = self._find_node_by_addr(child_addr)
            if child_node and not child_node.is_failed:
                if child_node.role == Roles.CLUSTER_HEAD:
                    if config.ENABLE_CLUSTER_DEBUG:
                        self.log(f"[ROUTER] Node {self.id}: Skipping orphan of {child_node.id} - already CH (accepted transfer)")
                    continue
                child_node.become_orphan(f"Parent node {self.id} became router (cannot accept children)")
                orphan_count += 1

        for node in ALL_NODES:
            if node.id == self.id or node.is_failed:
                continue
            if hasattr(node, 'parent_gui') and node.parent_gui == self.id:
                if node.role == Roles.CLUSTER_HEAD:
                    if config.ENABLE_CLUSTER_DEBUG:
                        self.log(f"[ROUTER] Node {self.id}: Skipping orphan of {node.id} - already CH (accepted transfer)")
                    continue
                if node.role != Roles.UNREGISTERED:
                    if node.role == Roles.REGISTERED:
                        node.become_orphan(f"Parent node {self.id} became router (cannot accept children)")
                        orphan_count += 1
                        if config.ENABLE_CLUSTER_DEBUG:
                            self.log(f"[ROUTER] Node {self.id}: Orphaned {node.id} (had us as parent_gui but not in members_table)")

        self.members_table = []
        if hasattr(self, 'node_addr_pool'):
            self.node_addr_pool = {}

        self.ch_addr = None
        self.set_role(Roles.ROUTER, reason=reason)

        if not hasattr(self, 'heartbeat_timer_active') or not self.heartbeat_timer_active:
            self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
            self.heartbeat_timer_active = True

        if config.ENABLE_CLUSTER_DEBUG:
            self.log(f"[ROUTER] Node {self.id} became ROUTER (prev_ch={format_addr(prev_ch_addr)}, orphaned {orphan_count} children)")
            write_log(self, f"[ROUTER] Node {self.id} activated as router (orphaned {orphan_count} children)")

    def find_farthest_member(self):
        if self.role != Roles.CLUSTER_HEAD or len(self.members_table) == 0:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[CH_TRANSFER] Node {self.id}: Cannot find candidate - role={self.role}, members={len(self.members_table)}")
            return None, None, -1

        member_addr_keys = {addr_key(addr) for addr in self.members_table if addr is not None}
        best_gui, best_addr, best_dist = None, None, -1.0
        candidates_checked = 0
        members_without_neighbor_info = []

        for neighbor_gui, neighbor_info in self.neighbors_table.items():
            neighbor_addr = neighbor_info.get('addr')

            if addr_key(neighbor_addr) not in member_addr_keys:
                continue

            candidates_checked += 1

            if neighbor_gui == ROOT_ID:
                continue

            distance = neighbor_info.get('distance')
            if distance is None:
                if config.ENABLE_CLUSTER_DEBUG:
                    self.log(f"[CH_TRANSFER] Node {self.id}: Neighbor {neighbor_gui} has no distance info")
                continue

            if distance > best_dist:
                best_gui = neighbor_gui
                best_addr = neighbor_addr
                best_dist = distance

        if best_gui is None and len(self.members_table) > 0:
            for member_addr in self.members_table:
                member_node = self._find_node_by_addr(member_addr)
                if member_node and member_node.id != ROOT_ID and member_node.id != self.id:
                    if self.id in NODE_POS and member_node.id in NODE_POS:
                        x1, y1 = NODE_POS[self.id]
                        x2, y2 = NODE_POS[member_node.id]
                        distance = math.hypot(x1 - x2, y1 - y2)
                        if distance > best_dist:
                            best_gui = member_node.id
                            best_addr = member_addr
                            best_dist = distance
                            members_without_neighbor_info.append((member_node.id, distance))

        if config.ENABLE_CLUSTER_DEBUG:
            if best_gui is None:
                self.log(f"[CH_TRANSFER] Node {self.id}: No suitable candidate found (checked {candidates_checked} in neighbors_table, {len(self.members_table)} total members)")
            else:
                source = "neighbors_table" if candidates_checked > 0 else "position_calculation"
                self.log(f"[CH_TRANSFER] Node {self.id}: Found candidate {best_gui} at distance {best_dist:.1f}m (from {source})")

        return best_gui, best_addr, best_dist

    def _trigger_ch_creation(self):
        if self.role != Roles.UNREGISTERED:
            return

        # Reduce cooldown for isolated nodes with many failed attempts
        adaptive_cooldown = self.trigger_ch_creation_cooldown
        if hasattr(self, 'failed_join_attempts') and self.failed_join_attempts >= 5:
            adaptive_cooldown = 20.0  # Reduce cooldown to 20s for very isolated nodes
            
        if self.last_trigger_ch_creation_time is not None:
            time_since_last = self.now - self.last_trigger_ch_creation_time
            if time_since_last < adaptive_cooldown:
                if config.ENABLE_CLUSTER_DEBUG:
                    self.log(f"[CH_CREATION] Node {self.id}: Rate-limiting TRIGGER_CH_CREATION (last sent {time_since_last:.1f}s ago, cooldown={adaptive_cooldown}s)")
                return

        found_registered = False
        for neighbor_gui, neighbor_info in self.neighbors_table.items():
            neighbor_role = neighbor_info.get('role')
            if neighbor_role == Roles.REGISTERED:
                found_registered = True
                trigger_pck = {
                    'dest': wsn.BROADCAST_ADDR,
                    'type': 'TRIGGER_CH_CREATION',
                    'source': self.addr if self.addr else wsn.BROADCAST_ADDR,
                    'gui': self.id,
                    'target_gui': neighbor_gui
                }
                self.send(trigger_pck)
                self.last_trigger_ch_creation_time = self.now
                self.log(f"[CH_CREATION] Node {self.id}: Sent TRIGGER_CH_CREATION broadcast (target REGISTERED neighbor {neighbor_gui})")
                break

        if not found_registered:
            trigger_pck = {
                'dest': wsn.BROADCAST_ADDR,
                'type': 'TRIGGER_CH_CREATION',
                'source': self.addr if self.addr else wsn.BROADCAST_ADDR,
                'gui': self.id,
                'target_gui': None
            }
            self.send(trigger_pck)
            self.last_trigger_ch_creation_time = self.now
            self.log(f"[CH_CREATION] Node {self.id}: Sent TRIGGER_CH_CREATION broadcast (no REGISTERED neighbors in table, hoping any REGISTERED node responds)")

    def initiate_ch_transfer(self):
        if not self.ch_transfer_enabled:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[CH_TRANSFER] Node {self.id}: Transfer disabled")
            return

        if self.ch_transfer_in_progress:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[CH_TRANSFER] Node {self.id}: Transfer already in progress")
            return

        if self.role != Roles.CLUSTER_HEAD:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[CH_TRANSFER] Node {self.id}: Not a CLUSTER_HEAD (role={self.role})")
            return

        if self.ch_addr is None:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[CH_TRANSFER] Node {self.id}: No ch_addr")
            return

        min_members = getattr(config, 'MIN_MEMBERS_FOR_TRANSFER', 1)
        if len(self.members_table) < min_members:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[CH_TRANSFER] Node {self.id}: Not enough members ({len(self.members_table)} < {min_members})")
            return

        candidate_gui, candidate_addr, candidate_dist = self.find_farthest_member()

        if candidate_gui is None:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[CH_TRANSFER] Node {self.id}: No candidate found (members={len(self.members_table)})")
            return

        self.ch_transfer_in_progress = True
        self.ch_transfer_candidate = candidate_gui

        transfer_pck = {
            'dest': candidate_addr,
            'type': 'CH_TRANSFER',
            'source': self.addr,
            'gui': self.id,
            'new_ch_addr': self.ch_addr,
            'prev_ch_addr': self.ch_addr
        }

        self.route_and_forward_package(transfer_pck)

        self.log(f"[CH_TRANSFER] Node {self.id} transferring CH role to node {candidate_gui} (dist={candidate_dist:.1f}m, addr={format_addr(candidate_addr)})")
        write_log(self, f"[CH_TRANSFER] Initiating transfer from CH {self.id} to member {candidate_gui} (dist={candidate_dist:.1f}m)")

    def fail_node(self):
        # Simulate node failure - node stops all operations.
        debug_log(f"data_collection_tree.py:{1320}", "fail_node() entry", {"node_id": self.id, "current_role": _role_name(self.role), "is_failed": self.is_failed, "is_root": self.role == Roles.ROOT}, "B")

        if self.is_failed or self.role == Roles.ROOT:
            debug_log(f"data_collection_tree.py:{1323}", "fail_node() early return - already failed or ROOT", {"node_id": self.id, "is_failed": self.is_failed, "is_root": self.role == Roles.ROOT}, "B")
            return

        if self.role not in [Roles.REGISTERED, Roles.CLUSTER_HEAD]:
            debug_log(f"data_collection_tree.py:{1326}", "fail_node() early return - wrong role", {"node_id": self.id, "role": _role_name(self.role), "required_roles": ["REGISTERED", "CLUSTER_HEAD"]}, "B")
            log_to_console_and_file(f"[FAILURE_SKIPPED] Node {self.id}: Failure skipped at {self.sim.now:.2f}s - not yet registered (role: {_role_name(self.role)})")
            if config.ENABLE_RECOVERY_DEBUG:
                self.log(f"[RECOVERY] Node {self.id} failure skipped - not yet registered (role: {_role_name(self.role)})")
            return

        self.is_failed = True
        self.failure_time = self.sim.now
        self.role_before_failure = self.role
        self.children_before_failure = list(self.members_table)

        FAILED_NODES.add(self.id)

        debug_log(f"data_collection_tree.py:{1339}", "Node marked as failed", {"node_id": self.id, "failure_time": self.failure_time, "FAILED_NODES": list(FAILED_NODES)}, "C")

        orphan_count = 0
        for child_addr in self.members_table:
            child_node = self._find_node_by_addr(child_addr)
            if child_node:
                child_node.become_orphan(f"Parent node {self.id} failed")
                orphan_count += 1

        self.kill_all_timers()

        self.scene.nodecolor(self.id, 1, 0, 0)

        self.set_timer('TIMER_FAILURE_HIGHLIGHT_END', config.FAILURE_HIGHLIGHT_DURATION)

        if config.ENABLE_RECOVERY_DEBUG:
            self.log(f"[RECOVERY] Node {self.id} FAILED at {self.sim.now:.2f}s | "
                    f"Role: {_role_name(self.role_before_failure)} | "
                    f"Orphaned children: {orphan_count}")

        log_role_change(self.id, self.role_before_failure, Roles.UNDISCOVERED,
                       self.sim.now, f"Node failed (orphaned {orphan_count} children)")

        if config.ENABLE_NETWORK_SNAPSHOTS and config.SNAPSHOT_T1_T2_AFTER_FAILURE:
            self.set_timer('TIMER_SNAPSHOT_T1_T2', config.SNAPSHOT_T1_T2_DELAY)

    def recover_node(self):
        # Simulate node recovery - node restarts and rejoins network.
        if not self.is_failed:
            return

        recovery_time = self.sim.now
        downtime = recovery_time - self.failure_time
        orphan_count = len([n for n in ALL_NODES if n.id in ORPHANED_NODES])

        self.is_failed = False
        FAILED_NODES.discard(self.id)

        log_recovery_event(self.id, self.failure_time, recovery_time,
                          orphan_count, self.role_before_failure, Roles.UNDISCOVERED)

        if config.ENABLE_RECOVERY_DEBUG:
            self.log(f"[RECOVERY] Node {self.id} RECOVERED at {recovery_time:.2f}s | "
                    f"Downtime: {downtime:.2f}s | "
                    f"Network orphans: {orphan_count}")

        self.scene.nodecolor(self.id, 1, 1, 1)
        self.addr = None
        self.ch_addr = None
        self.parent_gui = None
        self.members_table = []
        self.received_JR_guis = []
        self.neighbors_table = {}
        self.multihop_neighbor_table = {}
        self.hop_count = 99999
        self.set_role(Roles.UNDISCOVERED, reason=f"Node recovered after {downtime:.2f}s downtime")

        self.set_timer('TIMER_PROBE', 1)

        if config.ENABLE_NETWORK_SNAPSHOTS and config.SNAPSHOT_AT_T3_AFTER_RECOVERY:
            take_network_snapshot(f"At_T3_After_Recovery_Node_{self.id}", recovery_time)

    def become_orphan(self, reason=""):
        # Mark node as orphaned and initiate recovery.
        if self.is_failed or self.role == Roles.ROOT:
            return

        log_orphan_event(self.id, self.sim.now, reason, self.parent_gui)

        if config.ENABLE_RECOVERY_DEBUG:
            self.log(f"[RECOVERY] Node {self.id} became ORPHAN | Reason: {reason}")

        if not self.is_failed:
            self.scene.nodecolor(self.id, 1, 0.5, 0)
            self.set_timer('TIMER_ORPHAN_HIGHLIGHT_END', config.ORPHAN_HIGHLIGHT_DURATION)

        self.become_unregistered()

        for child_addr in list(self.members_table):
            child_node = self._find_node_by_addr(child_addr)
            if child_node and not child_node.is_failed:
                child_node.become_orphan(f"Parent node {self.id} became orphan")

    def _find_node_by_addr(self, addr):
        # Find node by network address.
        if addr is None:
            return None
        for node in ALL_NODES:
            if node.addr is not None and addr_equals(node.addr, addr):
                return node
        return None

    def _find_node_by_gui(self, gui):
        # Find node by GUI ID.
        if gui is None:
            return None
        for node in ALL_NODES:
            if node.id == gui:
                return node
        return None

    def _check_existing_ch_in_cluster(self, cluster_id):
        for neighbor_gui, neighbor_info in self.neighbors_table.items():
            neighbor_role = neighbor_info.get('role')
            neighbor_ch_addr = neighbor_info.get('ch_addr')

            if neighbor_role == Roles.CLUSTER_HEAD and neighbor_ch_addr is not None:
                if hasattr(neighbor_ch_addr, 'net_addr') and neighbor_ch_addr.net_addr == cluster_id:
                    return True, neighbor_gui

        return False, None

    def become_unregistered(self):
        if self.role != Roles.UNDISCOVERED:
            self.kill_all_timers()
            self.log('I became UNREGISTERED')
        self.scene.nodecolor(self.id, 1, 1, 0)
        self.erase_parent()
        self.addr = None
        self.ch_addr = None
        self.parent_gui = None
        self.root_addr = None
        self.set_role(Roles.UNREGISTERED)
        self.c_probe = 0
        self.th_probe = 10
        self.hop_count = 99999
        self.neighbors_table = {}
        
        # Update TX power to potentially boost for orphaned nodes
        self.update_cluster_tx_power()
        self.candidate_parents_table = []
        self.child_networks_table = {}
        self.members_table = []
        self.received_JR_guis = []
        self.failed_join_attempts = 0
        self.last_trigger_ch_creation_time = None
        self.send_probe()
        self.set_timer('TIMER_JOIN_REQUEST', 20)

    def _cleanup_stale_neighbors(self):
        # Remove neighbors that haven't sent heartbeats in a while to prevent memory bloat
        if not hasattr(self, 'neighbors_table') or not self.neighbors_table:
            return

        stale_timeout = config.HEARTH_BEAT_TIME_INTERVAL * 3
        current_time = self.now
        stale_neighbors = []
        for neighbor_gui, neighbor_info in self.neighbors_table.items():
            arrival_time = neighbor_info.get('arrival_time', 0)
            if current_time - arrival_time > stale_timeout:
                stale_neighbors.append(neighbor_gui)

        for neighbor_gui in stale_neighbors:
            del self.neighbors_table[neighbor_gui]
            if neighbor_gui in self.candidate_parents_table:
                self.candidate_parents_table.remove(neighbor_gui)
            if hasattr(self, 'multihop_neighbor_table') and neighbor_gui in self.multihop_neighbor_table:
                del self.multihop_neighbor_table[neighbor_gui]

        if stale_neighbors and config.ENABLE_NEIGHBOR_DEBUG:
            self.log(f"[NEIGHBOR_CLEANUP] Node {self.id}: Removed {len(stale_neighbors)} stale neighbors")

    def update_neighbor(self, pck):
        # Update 1-hop neighbor info from heartbeat and add to multihop table
        if not hasattr(self, '_last_neighbor_cleanup'):
            self._last_neighbor_cleanup = 0.0
        if self.now - self._last_neighbor_cleanup > 50.0:
            self._cleanup_stale_neighbors()
            self._last_neighbor_cleanup = self.now
        neighbor_entry = pck.copy()
        neighbor_entry['arrival_time'] = self.now
        if neighbor_entry['gui'] in NODE_POS and self.id in NODE_POS:
            x1, y1 = NODE_POS[self.id]
            x2, y2 = NODE_POS[neighbor_entry['gui']]
            neighbor_entry['distance'] = math.hypot(x1 - x2, y1 - y2)
        neighbor_entry['mesh_hop_distance'] = 1
        neighbor_gui = neighbor_entry['gui']
        old_entry = self.neighbors_table.get(neighbor_gui)
        self.neighbors_table[neighbor_gui] = neighbor_entry

        neighbor_role = neighbor_entry.get('role')
        neighbor_addr = neighbor_entry.get('source') or neighbor_entry.get('addr') or neighbor_entry.get('ch_addr')

        valid_roles = (Roles.CLUSTER_HEAD, Roles.ROOT)
        has_valid_role = (neighbor_role in valid_roles) if neighbor_role is not None else False
        has_valid_addr = (neighbor_addr is not None)
        can_be_parent = has_valid_role and has_valid_addr

        if neighbor_gui not in self.child_networks_table.keys():
            was_in_candidates = neighbor_gui in self.candidate_parents_table

            if can_be_parent:
                if neighbor_gui not in self.candidate_parents_table:
                    self.candidate_parents_table.append(neighbor_gui)
                    if self.role in (Roles.UNDISCOVERED, Roles.UNREGISTERED):
                        write_log(self, f"[JOIN] Node {self.id}: Added candidate parent {neighbor_gui} (role={neighbor_role}, addr={format_addr(neighbor_addr)})")
                elif old_entry and old_entry.get('role') != neighbor_role:
                    if self.role in (Roles.UNDISCOVERED, Roles.UNREGISTERED):
                        write_log(self, f"[JOIN] Node {self.id}: Candidate parent {neighbor_gui} role updated {old_entry.get('role')} -> {neighbor_role}")
            elif not can_be_parent and config.ENABLE_CLUSTER_DEBUG and self.role in (Roles.UNDISCOVERED, Roles.UNREGISTERED):
                reason = []
                if not has_valid_role:
                    reason.append(f"invalid_role={neighbor_role} (type={type(neighbor_role).__name__})")
                if not has_valid_addr:
                    reason.append("no_addr")
                if reason and len(self.candidate_parents_table) == 0 and len(self.neighbors_table) <= 5:
                    write_log(self, f"[JOIN] Node {self.id}: Neighbor {neighbor_gui} cannot be parent ({', '.join(reason)}, entry_keys={list(neighbor_entry.keys())})")

        if config.ENABLE_MULTIHOP_DISCOVERY:
            neighbor_gui = neighbor_entry['gui']
            euclidean_dist = neighbor_entry.get('distance', 0)

            self.multihop_neighbor_table[neighbor_gui] = {
                'hop_dist': 1,
                'next_hop': neighbor_gui,
                'distance': euclidean_dist,
                'addr': neighbor_entry.get('addr')
            }

            if config.ENABLE_NEIGHBOR_DEBUG:
                msg = f"[NEIGHBOR_1HOP] Discovered neighbor {neighbor_gui} at distance {euclidean_dist:.2f}m"
                self.log(msg)
                write_log(self, msg)

    def process_neighbor_share(self, pck):
        # Process neighbor info shared by neighbors (Distance Vector style)
        if not config.ENABLE_MULTIHOP_DISCOVERY:
            return

        sender_gui = pck['gui']
        neighbors_info = pck.get('neighbors_info', {})

        if sender_gui not in self.neighbors_table:
            return

        learned_count = 0

        for neighbor_gui, info in neighbors_info.items():
            if neighbor_gui == self.id:
                continue

            new_hop_dist = info['hop_dist'] + 1

            if new_hop_dist > config.MAX_HOP_DISTANCE:
                continue

            if neighbor_gui not in self.multihop_neighbor_table or \
               new_hop_dist < self.multihop_neighbor_table[neighbor_gui]['hop_dist']:

                self.multihop_neighbor_table[neighbor_gui] = {
                    'hop_dist': new_hop_dist,
                    'next_hop': sender_gui,
                    'distance': info['distance'],
                    'addr': info.get('addr')
                }
                learned_count += 1

                if config.ENABLE_NEIGHBOR_DEBUG:
                    msg = f"[NEIGHBOR_{new_hop_dist}HOP] Learned neighbor {neighbor_gui} via {sender_gui} (dist={info['distance']:.2f}m)"
                    self.log(msg)
                    write_log(self, msg)

        if config.ENABLE_NEIGHBOR_DEBUG and learned_count > 0:
            msg = f"[NEIGHBOR_SHARE] Learned {learned_count} neighbors from node {sender_gui}"
            self.log(msg)
            write_log(self, msg)

    def select_and_join(self):
        if self.role in (Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROUTER, Roles.ROOT):
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[JOIN] Node {self.id}: Skipping select_and_join - already {self.role}")
            return

        if len(self.candidate_parents_table) == 0:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[JOIN] Node {self.id}: No candidate parents available")
            return

        min_hop = 99999
        min_hop_gui = 99999
        for gui in self.candidate_parents_table:
            neighbor_info = self.neighbors_table.get(gui)
            if neighbor_info is None:
                continue
            neighbor_role = neighbor_info.get('role')
            valid_roles = (Roles.CLUSTER_HEAD, Roles.ROOT)
            if neighbor_role not in valid_roles:
                continue
            hop_count = neighbor_info.get('hop_count', 99999)
            if hop_count < min_hop or (hop_count == min_hop and gui < min_hop_gui):
                min_hop = hop_count
                min_hop_gui = gui
        if min_hop_gui == 99999:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[JOIN] Node {self.id}: No valid candidate found (checked {len(self.candidate_parents_table)} candidates)")
            return

        selected_entry = self.neighbors_table[min_hop_gui]
        selected_addr = selected_entry.get('source')
        if selected_addr is None:
            selected_addr = selected_entry.get('ch_addr')
        if selected_addr is None:
            selected_addr = selected_entry.get('addr')

        if selected_addr is None:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[JOIN] Node {self.id}: Selected candidate {min_hop_gui} has no address (entry keys: {list(selected_entry.keys())})")
            return

        if config.ENABLE_CLUSTER_DEBUG:
            self.log(f"[JOIN] Node {self.id}: Selected parent {min_hop_gui} (hop={min_hop}, addr={format_addr(selected_addr)})")

        self.send_join_request(selected_addr)

    def send_probe(self):
        self.send({'dest': wsn.BROADCAST_ADDR, 'type': 'PROBE'})

    def send_heart_beat(self):
        if self.role in (Roles.UNREGISTERED, Roles.UNDISCOVERED):
            return

        self.send({'dest': wsn.BROADCAST_ADDR,
                   'type': 'HEART_BEAT',
                   'source': self.ch_addr if self.ch_addr is not None else self.addr,
                   'gui': self.id,
                   'role': self.role,
                   'addr': self.addr,
                   'ch_addr': self.ch_addr,
                   'hop_count': self.hop_count})

    def share_neighbor_info(self):
        # Share multihop neighbor table with 1-hop neighbors (Distance Vector style)
        if not config.ENABLE_MULTIHOP_DISCOVERY:
            return

        if len(self.multihop_neighbor_table) == 0:
            return

        neighbors_to_share = {}
        for neighbor_gui, info in self.multihop_neighbor_table.items():
            if info['hop_dist'] < config.MAX_HOP_DISTANCE:
                neighbors_to_share[neighbor_gui] = {
                    'hop_dist': info['hop_dist'],
                    'distance': info['distance'],
                    'addr': info.get('addr')
                }

        if not neighbors_to_share:
            return

        if config.ENABLE_NEIGHBOR_DEBUG:
            msg = f"[NEIGHBOR_SHARE] Sharing {len(neighbors_to_share)} neighbors with 1-hop neighbors"
            self.log(msg)
            write_log(self, msg)

        self.send({
            'dest': wsn.BROADCAST_ADDR,
            'type': 'NEIGHBOR_SHARE',
            'gui': self.id,
            'neighbors_info': neighbors_to_share
        })

    def send_join_request(self, dest):
        old_time = self.last_join_request_sent_time
        self.last_join_request_sent_time = self.now
        self.send({'dest': dest, 'type': 'JOIN_REQUEST', 'gui': self.id})
        if config.ENABLE_CLUSTER_DEBUG:
            write_log(self, f"[JOIN] Node {self.id}: Sent JOIN_REQUEST to {format_addr(dest)}")

    def send_join_reply(self, gui, addr):
        self.send({'dest': wsn.BROADCAST_ADDR, 'type': 'JOIN_REPLY', 'source': self.ch_addr,
                   'gui': self.id, 'dest_gui': gui, 'addr': addr, 'root_addr': self.root_addr,
                   'hop_count': self.hop_count+1})

    def send_join_ack(self, dest):
        self.send({'dest': dest, 'type': 'JOIN_ACK', 'source': self.addr,
                   'gui': self.id})

    def send(self, pck):
        # Ensure every packet carries a creation timestamp and prevent routing loops.
        if self.is_shutdown:
            if config.ENABLE_ENERGY_DEBUG:
                p_type = pck.get('type', 'UNKNOWN')
                energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
                msg = f"[ENERGY] Node {self.id}: Cannot send {p_type} packet - node is shut down (energy={self.energy_remaining:.6f}J, {energy_percent:.2f}%, shutdown at {self.shutdown_time:.1f}s)"
                self.log(msg)
                write_log(self, msg)
            return

        if 'created_at' not in pck:
            pck['created_at'] = self.now
        p_type = pck.get('type', 'UNKNOWN')
        PACKET_STATS['total_attempts'] += 1
        PACKET_STATS['type_attempts'][p_type] += 1
        loss_rate = getattr(config, 'PACKET_LOSS_RATE', 0.0)
        if loss_rate > 0.0 and random.random() < loss_rate:
            msg = (f"[LOSS] Node {self.id}: Dropped packet type={pck.get('type')} "
                   f"dest={pck.get('dest')} rate={loss_rate:.3f}")
            self.debug_log(getattr(config, 'ENABLE_PACKET_LOSS_DEBUG', False), msg)
            write_log(self, msg)
            PACKET_STATS['total_dropped'] += 1
            PACKET_STATS['type_dropped'][p_type] += 1
            return

        if config.ENABLE_ENERGY_MODEL:
            packet_size = estimate_packet_size(pck)
            if self.ch_addr is not None:
                cluster_id = self.ch_addr.net_addr
                tx_power = get_cluster_tx_power(cluster_id)
            else:
                tx_power = self.tx_power_dbm
            tx_energy = calculate_tx_energy(packet_size, tx_power, include_pll_overhead=True)

            if self.energy_remaining >= tx_energy:
                self.energy_remaining -= tx_energy
                self.energy_tx_total += tx_energy

                if config.ENABLE_ENERGY_DEBUG:
                    energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
                    msg = f"[ENERGY] Node {self.id}: TX {p_type} ({packet_size}B, {tx_power}dBm) - {tx_energy*1e6:.3f}µJ, remaining={self.energy_remaining:.6f}J ({energy_percent:.2f}%)"
                    self.log(msg)
                    write_log(self, msg)
            else:
                if config.ENABLE_ENERGY_DEBUG:
                    msg = f"[ENERGY] Node {self.id}: Insufficient energy for TX {p_type} - need {tx_energy*1e6:.3f}µJ, have {self.energy_remaining*1e6:.3f}µJ"
                    self.log(msg)
                    write_log(self, msg)
                self.energy_remaining = 0.0
                self.shutdown_node("Insufficient energy for transmission")
                return

        route_trace = pck.get('route_trace', [])
        next_hop = pck.get('next_hop')
        dest = pck.get('dest')

        if self.addr is not None:
            if addr_equals(dest, self.addr) or addr_equals(next_hop, self.addr):
                if config.ENABLE_ROUTING_DEBUG:
                    self.log(f"[ROUTING] Node {self.id}: Packet for self (dest={format_addr(dest)}, next_hop={format_addr(next_hop)}), not sending to prevent loop")
                return

        is_broadcast = False
        if dest is not None and hasattr(dest, 'is_equal'):
            is_broadcast = dest.is_equal(wsn.BROADCAST_ADDR)

        has_specific_next_hop = (next_hop is not None and
                                not is_broadcast and
                                (not hasattr(next_hop, 'is_equal') or not next_hop.is_equal(wsn.BROADCAST_ADDR)))

        if has_specific_next_hop and route_trace:
            sent = False
            for (dist, node) in self.neighbor_distance_list:
                if dist <= self.tx_range:
                    if node.id == self.id:
                        continue
                    if node.can_receive(pck):
                        if node.addr is not None and addr_equals(node.addr, next_hop):
                            prop_time = dist / 1000000 - 0.00001 if dist / 1000000 - 0.00001 > 0 else 0.00001
                            self.delayed_exec(prop_time, node.on_receive_check, pck)
                            sent = True
                            if config.ENABLE_ROUTING_DEBUG and node.id in route_trace:
                                self.log(f"[ROUTING] Node {self.id}: Sending to intended next_hop {node.id} (in route_trace but routing decision trusted)")
                            break
                else:
                    break
            if not sent:
                if config.ENABLE_ROUTING_DEBUG:
                    self.log(f"[ROUTING] Node {self.id}: Intended next_hop {format_addr(next_hop)} not found in neighbors")
            return

        if route_trace and not is_broadcast:
            filtered_neighbors = []
            for (dist, node) in self.neighbor_distance_list:
                if dist <= self.tx_range:
                    if node.id in route_trace:
                        if config.ENABLE_ROUTING_DEBUG:
                            self.log(f"[ROUTING] Node {self.id}: Skipping neighbor {node.id} - already in route_trace {route_trace}")
                        continue
                    if node.can_receive(pck):
                        filtered_neighbors.append((dist, node))
                else:
                    break

            if filtered_neighbors:
                for (dist, node) in filtered_neighbors:
                    prop_time = dist / 1000000 - 0.00001 if dist / 1000000 - 0.00001 > 0 else 0.00001
                    self.delayed_exec(prop_time, node.on_receive_check, pck)
            else:
                if config.ENABLE_ROUTING_DEBUG:
                    self.log(f"[ROUTING] Node {self.id}: No valid neighbors (all in route_trace {route_trace})")
            return

        super().send(pck)

    def shutdown_node(self, reason="Low energy"):
        if self.is_shutdown:
            if config.ENABLE_ENERGY_DEBUG:
                msg = f"[ENERGY] Node {self.id}: Already shut down (attempted shutdown: {reason})"
                self.log(msg)
                write_log(self, msg)
            return

        self.is_shutdown = True
        self.shutdown_time = self.now

        self.scene.nodecolor(self.id, 0.3, 0.3, 0.3)

        energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
        total_consumed = self.energy_tx_total + self.energy_rx_total + self.energy_baseline_total
        tx_percent = (self.energy_tx_total / total_consumed * 100) if total_consumed > 0 else 0
        rx_percent = (self.energy_rx_total / total_consumed * 100) if total_consumed > 0 else 0
        baseline_percent = (self.energy_baseline_total / total_consumed * 100) if total_consumed > 0 else 0

        msg = (f"[ENERGY] Node {self.id}: SHUTDOWN - {reason} "
               f"(energy={self.energy_remaining:.6f}J, {energy_percent:.2f}% remaining, "
               f"consumed={total_consumed:.6f}J: TX={tx_percent:.1f}%, RX={rx_percent:.1f}%, Baseline={baseline_percent:.1f}%, "
               f"lifetime={self.shutdown_time:.1f}s)")
        self.log(msg)
        write_log(self, msg)

    def check_energy_level(self):
        # Check if node energy is below minimum threshold and shutdown if needed.
        if not config.ENABLE_ENERGY_MODEL:
            return

        if self.energy_remaining < config.BATTERY_ENERGY_MIN and not self.is_shutdown:
            if config.ENABLE_ENERGY_DEBUG:
                energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
                msg = f"[ENERGY] Node {self.id}: Energy check - {self.energy_remaining:.6f}J ({energy_percent:.2f}%) below threshold {config.BATTERY_ENERGY_MIN:.6f}J"
                self.log(msg)
                write_log(self, msg)
            self.shutdown_node(f"Energy below minimum threshold ({config.BATTERY_ENERGY_MIN:.6f}J)")

    def update_cluster_tx_power(self):
        # Update TX power based on cluster assignment and orphan status.
        if self.ch_addr is not None:
            cluster_id = self.ch_addr.net_addr
            self.cluster_tx_power_dbm = get_cluster_tx_power(cluster_id)
            self.tx_power_dbm = self.cluster_tx_power_dbm

            if config.ENABLE_ENERGY_DEBUG:
                msg = f"[ENERGY] Node {self.id}: Updated TX power to {self.tx_power_dbm} dBm (cluster {cluster_id})"
                self.log(msg)
                write_log(self, msg)
        else:
            # Check if adaptive TX power boost is enabled for orphaned nodes
            if (hasattr(config, 'ADAPTIVE_TX_POWER_FOR_ORPHANS') and 
                config.ADAPTIVE_TX_POWER_FOR_ORPHANS and 
                self.role == Roles.UNREGISTERED and
                hasattr(self, 'failed_join_attempts') and 
                self.failed_join_attempts >= 2):
                
                # Boost TX power for isolated/orphaned nodes
                boost = getattr(config, 'ORPHAN_TX_POWER_BOOST', 5)
                boosted_power = config.TX_POWER_DEFAULT + boost
                self.tx_power_dbm = min(config.TX_POWER_MAX, boosted_power)
                
                if config.ENABLE_ENERGY_DEBUG:
                    msg = f"[TX_POWER] Node {self.id}: ORPHAN BOOST - TX power increased to {self.tx_power_dbm}dBm (+{boost}dBm boost, {self.failed_join_attempts} failed attempts)"
                    self.log(msg)
                    write_log(self, msg)
            else:
                self.tx_power_dbm = config.TX_POWER_DEFAULT

    def route_and_forward_package(self, pck):
        debug_log(f"data_collection_tree.py:{2074}", "route_and_forward_package entry", {"node_id": self.id, "packet_type": pck.get('type'), "dest": format_addr(pck.get('dest')), "mesh_enabled": config.ENABLE_MESH_ROUTING, "tree_enabled": config.ENABLE_TREE_ROUTING, "route_trace": pck.get('route_trace', [])}, "A")

        if 'created_at' not in pck:
            pck['created_at'] = self.now
        dest = pck.get('dest')
        if dest is None:
            self.debug_log(
                config.ENABLE_ROUTING_DEBUG,
                f"[ROUTING] Node {self.id}: Cannot route packet without destination (type={pck.get('type')})"
            )
            write_log(self, f"ROUTE_FAIL type={pck.get('type')} reason=no_dest")
            return

        if dest is not None and hasattr(dest, 'is_equal'):
            if dest.is_equal(wsn.BROADCAST_ADDR):
                if config.ENABLE_ROUTING_DEBUG:
                    pck['next_hop'] = dest
                    self._record_route(pck, 'LOCAL_BROADCAST', dest)
                return

        route_trace = pck.setdefault('route_trace', [])

        if not route_trace or route_trace[-1] != self.id:
            route_trace.append(self.id)

        visit_count = route_trace.count(self.id)
        if visit_count > 1:
            if config.ENABLE_ROUTING_DEBUG:
                self.log(f"[ROUTING] Node {self.id}: Dropping packet - loop detected (visited {visit_count} times, trace: {route_trace})")
            write_log(self, f"ROUTE_FAIL type={pck.get('type')} reason=loop")
            return

        if len(route_trace) > 20:
            if config.ENABLE_ROUTING_DEBUG:
                self.log(f"[ROUTING] Node {self.id}: Dropping packet - too many hops ({len(route_trace)})")
            write_log(self, f"ROUTE_FAIL type={pck.get('type')} reason=too_many_hops")
            return

        if self.addr is not None and addr_equals(dest, self.addr):
            pck['next_hop'] = dest
            self._record_route(pck, 'LOCAL_SELF', dest)
            return

        path_str = "UNKNOWN"

        if config.ENABLE_MESH_ROUTING:
            neighbor_match = next(
                (entry for entry in self.neighbors_table.values()
                 if addr_equals(entry.get('addr'), dest) or addr_equals(entry.get('ch_addr'), dest)),
                None
            )

            multihop_match = None
            if neighbor_match is None and config.ENABLE_MULTIHOP_DISCOVERY:
                multihop_match = next(
                    (info for gui, info in self.multihop_neighbor_table.items()
                     if addr_equals(info.get('addr'), dest)),
                    None
                )
                if multihop_match:
                    next_gui = multihop_match.get('next_hop')
                    next_entry = self.neighbors_table.get(next_gui)
                    if next_entry:
                        next_addr = next_entry.get('addr')
                        if next_addr is not None:
                            pck['next_hop'] = next_addr
                            path_str = f"MESH_{multihop_match.get('hop_dist', 2)}H"
                            self._record_route(pck, path_str, next_addr)
                            self.send(pck)
                        return

            if neighbor_match:
                if addr_equals(dest, self.addr):
                    if config.ENABLE_ROUTING_DEBUG:
                        self.log(f"[ROUTING] Node {self.id}: Mesh routing detected packet for self, not routing")
                    return

                if neighbor_match.get('neighbor_hop_count', 1) > 1:
                    next_hop_gui = neighbor_match.get('next_hop')
                    if next_hop_gui:
                        next_hop_entry = self.neighbors_table.get(next_hop_gui)
                        if next_hop_entry:
                            pck['next_hop'] = next_hop_entry.get('addr', dest)
                            path_str = "MESH"
                        else:
                            pck['next_hop'] = dest
                            path_str = "MESH"
                    else:
                        pck['next_hop'] = dest
                        path_str = "MESH"
                else:
                    pck['next_hop'] = dest
                    path_str = "DIRECT"

                if not addr_equals(pck.get('next_hop'), self.addr):
                    self._record_route(pck, path_str, pck['next_hop'])
                    self.send(pck)
                return
        else:
            debug_log(f"data_collection_tree.py:{2195}", "Mesh routing disabled, skipping to tree routing", {"node_id": self.id, "packet_type": pck.get('type'), "dest": format_addr(dest)}, "B")
            if config.ENABLE_ROUTING_DEBUG:
                self.debug_log(True, f"[ROUTING] Node {self.id}: Mesh routing disabled, using tree routing only")

        if config.ENABLE_TREE_ROUTING:
            debug_log(f"data_collection_tree.py:{2201}", "Tree routing check start", {"node_id": self.id, "role": _role_name(self.role), "has_parent": self.parent_gui is not None, "parent_gui": self.parent_gui, "ch_addr": format_addr(self.ch_addr), "members_count": len(self.members_table), "child_networks_count": len(self.child_networks_table)}, "C")
            if self.role in (Roles.CLUSTER_HEAD, Roles.ROOT):
                debug_log(f"data_collection_tree.py:{2203}", "Tree STEP 4: Checking members_table", {"node_id": self.id, "members_table": [format_addr(m) for m in self.members_table], "dest": format_addr(dest)}, "D")
                member_match = next(
                    (entry for entry in self.members_table if entry == dest),
                    None
                )
                if member_match:
                    debug_log(f"data_collection_tree.py:{2208}", "Tree STEP 4: MATCH - routing to cluster member", {"node_id": self.id, "next_hop": format_addr(dest), "path": "CLUSTER_MEMBER"}, "D")
                    pck['next_hop'] = dest
                    path_str = "CLUSTER_MEMBER"
                    self._record_route(pck, path_str, dest)
                    self.send(pck)
                    return

            if self.ch_addr is not None and hasattr(dest, 'net_addr'):
                debug_log(f"data_collection_tree.py:{2215}", "Tree STEP 5: Checking same cluster", {"node_id": self.id, "my_cluster": self.ch_addr.net_addr if self.ch_addr else None, "dest_cluster": dest.net_addr if hasattr(dest, 'net_addr') else None}, "E")
                if dest.net_addr == self.ch_addr.net_addr:
                    debug_log(f"data_collection_tree.py:{2217}", "Tree STEP 5: MATCH - same cluster, routing directly", {"node_id": self.id, "next_hop": format_addr(dest), "path": "TREE_SAME_CLUSTER"}, "E")
                    pck['next_hop'] = dest
                    path_str = "TREE_SAME_CLUSTER"
                    self._record_route(pck, path_str, dest)
                    self.send(pck)
                    return

            if self.ch_addr is not None:
                debug_log(f"data_collection_tree.py:{2224}", "Tree STEP 6: Checking child_networks_table", {"node_id": self.id, "child_networks": {gui: list(nets) for gui, nets in self.child_networks_table.items()}, "dest_cluster": dest.net_addr if hasattr(dest, 'net_addr') else None}, "F")
                for child_gui, child_networks in self.child_networks_table.items():
                    if hasattr(dest, 'net_addr') and dest.net_addr in child_networks:
                        child_info = self.neighbors_table.get(child_gui)
                        if child_info:
                            debug_log(f"data_collection_tree.py:{2228}", "Tree STEP 6: MATCH - routing to child", {"node_id": self.id, "child_gui": child_gui, "next_hop": format_addr(child_info.get('addr')), "path": "TREE_CHILD"}, "F")
                            pck['next_hop'] = child_info.get('addr')
                            path_str = "TREE_CHILD"
                            self._record_route(pck, path_str, pck['next_hop'])
                            self.send(pck)
                            return

            if self.role != Roles.ROOT and self.parent_gui is not None:
                debug_log(f"data_collection_tree.py:{2236}", "Tree STEP 7: Routing to parent (fallback)", {"node_id": self.id, "parent_gui": self.parent_gui, "role": _role_name(self.role)}, "G")
                parent_info = self.neighbors_table.get(self.parent_gui)
                if parent_info:
                    debug_log(f"data_collection_tree.py:{2239}", "Tree STEP 7: MATCH - routing to parent", {"node_id": self.id, "parent_gui": self.parent_gui, "next_hop": format_addr(parent_info.get('ch_addr') or parent_info.get('addr')), "path": "TREE_PARENT"}, "G")
                    pck['next_hop'] = parent_info.get('ch_addr') or parent_info.get('addr')
                    path_str = "TREE_PARENT"
                    self._record_route(pck, path_str, pck['next_hop'])
                    self.send(pck)
                    return
                else:
                    debug_log(f"data_collection_tree.py:{2244}", "Tree STEP 7: FAILED - parent_info not found", {"node_id": self.id, "parent_gui": self.parent_gui}, "G")
        else:
            if config.ENABLE_ROUTING_DEBUG:
                self.debug_log(True, f"[ROUTING] Node {self.id}: Tree routing disabled, no route available")

        debug_log(f"data_collection_tree.py:{2250}", "NO_ROUTE found", {"node_id": self.id, "packet_type": pck.get('type'), "dest": format_addr(dest), "role": _role_name(self.role), "has_parent": self.parent_gui is not None, "is_root": self.role == Roles.ROOT}, "H")
        self.debug_log(config.ENABLE_ROUTING_DEBUG,
                      f"[ROUTING] Node {self.id}: NO_ROUTE for type={pck.get('type')} dest={format_addr(dest)}")
        write_log(self, f"ROUTE_FAIL type={pck.get('type')} dest={format_addr(dest)}")

    def _get_parent_next_hop(self):
        if self.role == Roles.ROOT or self.parent_gui is None:
            return None
        parent_info = self.neighbors_table.get(self.parent_gui)
        if not parent_info:
            return None
        return parent_info.get('addr') or parent_info.get('ch_addr')

    def _record_route(self, pck, path_label, next_hop):
        if config.ENABLE_ROUTING_DEBUG:
            msg = f"[ROUTING] Node {self.id}: {path_label} -> dest={format_addr(pck.get('dest'))} next={format_addr(next_hop)}"
            self.log(msg)
            write_log(self, msg)
        log_packet_route(pck, self, format_addr(next_hop), path_label)

    def send_network_request(self):
        if self.root_addr is None:
            self.debug_log(config.ENABLE_ROUTING_DEBUG,
                           f"[ROUTING] Node {self.id}: Cannot send NETWORK_REQUEST - root_addr unknown")
            write_log(self, "ROUTE_FAIL type=NETWORK_REQUEST reason=no_root_addr")
            return
        if self.addr is None:
            self.debug_log(config.ENABLE_ROUTING_DEBUG,
                           f"[ROUTING] Node {self.id}: Cannot send NETWORK_REQUEST - addr not assigned")
            write_log(self, "ROUTE_FAIL type=NETWORK_REQUEST reason=no_addr")
            return
        self.route_and_forward_package({'dest': self.root_addr, 'type': 'NETWORK_REQUEST', 'source': self.addr, 'gui': self.id})

    def send_network_reply(self, dest, addr):
        self.route_and_forward_package({'dest': dest, 'type': 'NETWORK_REPLY', 'source': self.addr, 'addr': addr})

    def send_network_update(self):
        if self.role == Roles.ROOT or self.parent_gui is None:
            return

        parent_addr = self._get_parent_next_hop()
        if parent_addr is None:
            return

        child_networks = []
        if self.ch_addr is not None:
            child_networks = [self.ch_addr.net_addr]
        for networks in self.child_networks_table.values():
            child_networks.extend(networks)

        child_networks_sorted = sorted(set(child_networks))

        if self.last_child_networks_sent == child_networks_sorted:
            return

        if self.last_network_update_sent_time is not None:
            time_since_last = self.now - self.last_network_update_sent_time
            if time_since_last < self.network_update_cooldown:
                return

        self.last_network_update_sent_time = self.now
        self.last_child_networks_sent = child_networks_sorted
        pck = {'dest': parent_addr, 'type': 'NETWORK_UPDATE', 'source': self.addr,
               'gui': self.id, 'child_networks': child_networks}
        self.route_and_forward_package(pck)

    def send_random_data_packet(self):
        # Pick a random destination node and trace the routed path.
        if self.addr is None or self.id == ROOT_ID:
            return
        root_node = next((n for n in ALL_NODES if n.id == ROOT_ID and getattr(n, "addr", None)), None)
        if root_node is None or self.root_addr is None:
            self.debug_log(config.ENABLE_ROUTING_DEBUG,
                           f"[DATA] Node {self.id}: Root not ready for SENSOR_DATA deliveries")
            return

        packet_id = next_packet_id()
        pck = {
            'packet_id': packet_id,
            'type': 'SENSOR_DATA',
            'source': self.addr,
            'source_gui': self.id,
            'dest': root_node.addr,
            'dest_gui': root_node.id,
            'sensor_value': random.uniform(0, 100),
            'route_trace': [],
        }
        self.debug_log(config.ENABLE_ROUTING_DEBUG,
                       f"[DATA] Node {self.id}: Sending packet#{packet_id} to ROOT Node {root_node.id}")
        self.route_and_forward_package(pck)

    def _init_address_pool(self):
        # Initialize address pool for cluster head - simple and clean.
        self.node_addr_pool = {i: None for i in range(1, config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER + 1)}
        self.log(f"[CLUSTER_SIZE] Node {self.id}: Initialized address pool with {config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER} slots")

    def _assign_child_address(self, child_gui):
        # Assign an address to a child node
        for node_addr, assigned_gui in self.node_addr_pool.items():
            if assigned_gui is None or assigned_gui == child_gui:
                self.node_addr_pool[node_addr] = child_gui
                child_addr = wsn.Addr(self.ch_addr.net_addr, node_addr)
                self.log(f"[CLUSTER_SIZE] Node {self.id}: Assigned address {child_addr} to child {child_gui} (slot {node_addr}/{config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER})")
                return child_addr

        self.log(f"[CLUSTER_SIZE] Node {self.id}: CLUSTER FULL! Cannot assign address to child {child_gui}")
        return None

    def on_receive(self, pck):
        if self.is_shutdown:
            if config.ENABLE_ENERGY_DEBUG and pck.get('type') not in ('HEART_BEAT',):
                msg = f"[ENERGY] Node {self.id}: Ignoring {pck.get('type', 'UNKNOWN')} packet - node is shut down"
                self.log(msg)
                write_log(self, msg)
            return

        if self.is_failed:
            return

        if config.ENABLE_ENERGY_MODEL:
            packet_size = estimate_packet_size(pck)
            rx_energy = calculate_rx_energy(packet_size, include_pll_overhead=True)

            if self.energy_remaining >= rx_energy:
                self.energy_remaining -= rx_energy
                self.energy_rx_total += rx_energy
                if config.ENABLE_ENERGY_DEBUG and pck.get('type') != 'HEART_BEAT':
                    energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
                    msg = f"[ENERGY] Node {self.id}: RX {pck.get('type', 'UNKNOWN')} ({packet_size}B) - {rx_energy*1e6:.3f}µJ, remaining={self.energy_remaining:.6f}J ({energy_percent:.2f}%)"
                    self.log(msg)
                    write_log(self, msg)
            else:
                if config.ENABLE_ENERGY_DEBUG:
                    msg = f"[ENERGY] Node {self.id}: Insufficient energy for RX {pck.get('type', 'UNKNOWN')} - need {rx_energy*1e6:.3f}µJ, have {self.energy_remaining*1e6:.3f}µJ"
                    self.log(msg)
                    write_log(self, msg)
                self.energy_remaining = 0.0
                self.shutdown_node("Insufficient energy for reception")
                return

        dest = pck.get('dest')
        is_final = False
        if pck.get('type') == 'JOIN_REPLY' and pck.get('dest_gui') == self.id:
            is_final = True
        elif self.addr is not None and addr_equals(dest, self.addr):
            is_final = True
        elif self.ch_addr is not None and addr_equals(dest, self.ch_addr):
            is_final = True
        if is_final:
            route = pck.setdefault('route_trace', [])
            if not route or route[-1] != self.id:
                route.append(self.id)
            log_packet_delivery(pck, self)
            record_packet_path(pck, self)

        if self.role == Roles.ROOT or self.role == Roles.CLUSTER_HEAD:
            dest = pck.get('dest')

            is_broadcast = False
            if dest is not None and hasattr(dest, 'is_equal'):
                is_broadcast = dest.is_equal(wsn.BROADCAST_ADDR)
            is_for_self = addr_equals(dest, self.addr) or addr_equals(dest, self.ch_addr)

            if not is_broadcast and 'next_hop' in pck.keys() and not is_for_self:
                self.route_and_forward_package(pck)
                return
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'NEIGHBOR_SHARE':
                self.process_neighbor_share(pck)
            if pck['type'] == 'PROBE':
                self.send_heart_beat()
            if pck['type'] == 'JOIN_REQUEST':
                child_gui = pck.get('gui')

                child_already_assigned = any(assigned_gui == child_gui for assigned_gui in self.node_addr_pool.values())
                if child_already_assigned:
                    child_node = self._find_node_by_gui(child_gui)
                    if child_node and child_node.role in (Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROUTER):
                        if config.ENABLE_CLUSTER_DEBUG:
                            self.log(f"[CLUSTER_SIZE] Node {self.id}: Ignoring JOIN_REQUEST from already-registered child {child_gui} (role={child_node.role})")
                        return

                    existing_addr = None
                    for node_addr, assigned_gui in self.node_addr_pool.items():
                        if assigned_gui == child_gui:
                            existing_addr = wsn.Addr(self.ch_addr.net_addr, node_addr)
                            break
                    if existing_addr is not None:
                        last_sent = self.join_reply_last_sent.get(child_gui, 0)
                        time_since_last = self.now - last_sent
                        if time_since_last >= self.join_reply_cooldown:
                            self.send_join_reply(child_gui, existing_addr)
                            self.join_reply_last_sent[child_gui] = self.now
                            if config.ENABLE_CLUSTER_DEBUG:
                                self.log(f"[CLUSTER_SIZE] Node {self.id}: Resending JOIN_REPLY to child {child_gui} (already assigned {existing_addr}, cooldown={time_since_last:.1f}s)")
                    return

                current_children = sum(1 for assigned_gui in self.node_addr_pool.values()
                                     if assigned_gui is not None)

                if current_children >= config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER:
                    self.debug_log(config.ENABLE_CLUSTER_DEBUG,
                                 f"[CLUSTER_SIZE] Node {self.id}: CLUSTER FULL! Cannot accept child {child_gui} "
                                 f"(current={current_children}/{config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER})")
                else:
                    child_addr = self._assign_child_address(child_gui)
                    if child_addr is not None:
                        self.send_join_reply(child_gui, child_addr)
                    else:
                        self.log(f"[CLUSTER_SIZE] Node {self.id}: ERROR - Pool allocation failed for child {child_gui}")
            if pck['type'] == 'NETWORK_REQUEST':
                if self.role == Roles.ROOT:
                    cluster_id = None
                    for cid, assigned_source in self.cluster_addr_pool.items():
                        if assigned_source is None or assigned_source == pck['source']:
                            cluster_id = cid
                            self.cluster_addr_pool[cid] = pck['source']
                            break

                    if cluster_id is not None:
                        new_addr = wsn.Addr(cluster_id, 254)
                        request_gui = pck.get('gui')
                        self.log(f"[CLUSTER_SIZE] ROOT Node {self.id}: Assigned cluster ID {cluster_id} to {pck['source']} (node {request_gui})")
                        route_trace = pck.get('route_trace', [])
                        if route_trace and len(route_trace) > 1:
                            prev_hop_gui = route_trace[-2]
                            prev_hop_info = self.neighbors_table.get(prev_hop_gui)
                            if prev_hop_info:
                                reply_pck = {'dest': pck['source'], 'type': 'NETWORK_REPLY', 'source': self.addr, 'addr': new_addr, 'route_trace': [self.id]}
                                reply_pck['next_hop'] = prev_hop_info.get('addr')
                                self._record_route(reply_pck, 'TREE_REVERSE', reply_pck['next_hop'])
                                self.send(reply_pck)
                            else:
                                self.send_network_reply(pck['source'], new_addr)
                        else:
                            self.send_network_reply(pck['source'], new_addr)
                    else:
                        self.log(f"[CLUSTER_SIZE] ROOT Node {self.id}: ERROR - No available cluster IDs! All {config.NUM_OF_CLUSTERS} clusters in use")
            if pck['type'] == 'JOIN_ACK':
                member_addr = pck.get('source')
                if member_addr is not None and len(self.members_table) < config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER:
                    if member_addr not in self.members_table:
                        self.members_table.append(member_addr)
                        self.log(f"[MEMBER_TABLE] Node {self.id}: Added member {member_addr} (size={len(self.members_table)}/{config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER})")
                        if self.role == Roles.CLUSTER_HEAD and self.ch_transfer_enabled and self.id != ROOT_ID:
                            self.set_timer('TIMER_CH_TRANSFER_DELAY', 2)
                        else:
                            if config.ENABLE_CLUSTER_DEBUG:
                                self.log(f"[CH_TRANSFER] Node {self.id}: Skipping transfer - role={self.role}, enabled={self.ch_transfer_enabled}, is_root={self.id == ROOT_ID}")
                    else:
                        if config.ENABLE_CLUSTER_DEBUG:
                            self.log(f"[MEMBER_TABLE] Node {self.id}: Member {member_addr} already in table")
                elif member_addr is not None:
                    self.log(f"[MEMBER_TABLE] Node {self.id}: REJECTED {member_addr} - members_table FULL")
            if pck['type'] == 'CH_TRANSFER_ACK':
                is_for_us = (addr_equals(pck.get('dest'), self.addr) or
                            addr_equals(pck.get('dest'), self.ch_addr))
                if is_for_us and self.ch_transfer_in_progress and pck.get('gui') == self.ch_transfer_candidate:
                    new_ch_gui = pck.get('gui')
                    new_ch_node = self._find_node_by_gui(new_ch_gui)
                    if new_ch_node and new_ch_node.addr is not None:
                        if new_ch_node.addr in self.members_table:
                            self.members_table.remove(new_ch_node.addr)
                            if config.ENABLE_CLUSTER_DEBUG:
                                self.log(f"[CH_TRANSFER] Node {self.id}: Removed new CH {new_ch_gui} from members_table before becoming router")
                        if hasattr(self, 'node_addr_pool'):
                            for node_addr, assigned_gui in list(self.node_addr_pool.items()):
                                if assigned_gui == new_ch_gui:
                                    self.node_addr_pool[node_addr] = None
                                    if config.ENABLE_CLUSTER_DEBUG:
                                        self.log(f"[CH_TRANSFER] Node {self.id}: Freed address slot {node_addr} (new CH {new_ch_gui})")

                    if config.ENABLE_CLUSTER_DEBUG:
                        self.log(f"[CH_TRANSFER] Node {self.id} received CH_TRANSFER_ACK from {pck.get('gui')}, becoming router")
                        write_log(self, f"[CH_TRANSFER] Node {self.id} received ACK from {pck.get('gui')}, becoming router")
                    self.become_router("CH transfer ACK received")
                    self.ch_transfer_in_progress = False
                    self.ch_transfer_candidate = None
            if pck['type'] == 'NETWORK_UPDATE':
                sender_gui = pck.get('gui')
                new_networks = pck.get('child_networks', [])
                old_networks = self.child_networks_table.get(sender_gui, [])

                if sorted(set(new_networks)) != sorted(set(old_networks)):
                    self.child_networks_table[sender_gui] = new_networks
                    if self.role != Roles.ROOT:
                        self.send_network_update()
            if pck['type'] in ('SENSOR', 'SENSOR_DATA'):
                pass
        elif self.role == Roles.REGISTERED:
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'NEIGHBOR_SHARE':
                self.process_neighbor_share(pck)
            if pck['type'] == 'PROBE':
                self.send_heart_beat()
            if pck['type'] == 'JOIN_REQUEST':
                if pck['gui'] not in self.received_JR_guis:
                    self.received_JR_guis.append(pck['gui'])

                    if self.ch_addr is not None:
                        child_gui = pck['gui']
                        child_addr = self._assign_child_address(child_gui)
                        if child_addr is not None:
                            self.send_join_reply(child_gui, child_addr)
                            write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Sent JOIN_REPLY to child {child_gui} (addr={format_addr(child_addr)})")
                        else:
                            write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Cluster full, cannot accept child {child_gui}")
                    else:
                        should_become_ch = False
                        reason = ""

                        if self.parent_gui is not None:
                            parent_info = self.neighbors_table.get(self.parent_gui)
                            if parent_info:
                                parent_role = parent_info.get('role')
                                if parent_role in (Roles.CLUSTER_HEAD, Roles.ROOT):
                                    parent_node = self._find_node_by_gui(self.parent_gui)
                                    if parent_node and hasattr(parent_node, 'node_addr_pool'):
                                        current_children = sum(1 for assigned_gui in parent_node.node_addr_pool.values()
                                                             if assigned_gui is not None)
                                        if current_children >= config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER:
                                            should_become_ch = True
                                            reason = f"parent CH {self.parent_gui} is full ({current_children}/{config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER})"
                                else:
                                    should_become_ch = True
                                    reason = f"parent {self.parent_gui} is not CH/ROOT (role={parent_role})"
                            else:
                                should_become_ch = True
                                reason = f"parent {self.parent_gui} not in neighbors_table"
                        else:
                            should_become_ch = True
                            reason = "no parent available"

                        if not should_become_ch and self.hop_count is not None and self.hop_count >= 4:
                            should_become_ch = True
                            reason = f"far from ROOT (hop_count={self.hop_count}, reducing latency)"

                        if should_become_ch:
                            temp_cluster_id = (self.id % (config.NUM_OF_CLUSTERS - 1)) + 1

                            existing_ch, existing_ch_gui = self._check_existing_ch_in_cluster(temp_cluster_id)
                            if existing_ch:
                                existing_ch_info = self.neighbors_table.get(existing_ch_gui)
                                if existing_ch_info:
                                    existing_ch_addr = existing_ch_info.get('ch_addr') or existing_ch_info.get('addr')
                                    if existing_ch_addr:
                                        forward_pck = pck.copy()
                                        forward_pck['source'] = self.addr
                                        forward_pck['gui'] = pck['gui']
                                        forward_pck['dest'] = existing_ch_addr
                                        self.route_and_forward_package(forward_pck)
                                        write_log(self, f"[CH_CREATION] Node {self.id}: CH {existing_ch_gui} already exists with cluster {temp_cluster_id}, forwarding JOIN_REQUEST to it")
                                        return

                            write_log(self, f"[CH_CREATION] Node {self.id}: Received JOIN_REQUEST from {pck['gui']}, becoming CH ({reason})")
                            self.ch_addr = wsn.Addr(temp_cluster_id, 254)
                            self.set_role(Roles.CLUSTER_HEAD, reason=f"CH creation for JOIN_REQUEST: {reason}")
                            self._init_address_pool()

                            self.send_heart_beat()
                            if not hasattr(self, 'heartbeat_timer_active') or not self.heartbeat_timer_active:
                                self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                                self.heartbeat_timer_active = True

                            if config.ENABLE_MULTIHOP_DISCOVERY:
                                self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)

                            self.send_network_request()

                            child_gui = pck['gui']
                            child_addr = self._assign_child_address(child_gui)
                            if child_addr is not None:
                                self.send_join_reply(child_gui, child_addr)
                                write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Sent JOIN_REPLY to child {child_gui} (addr={format_addr(child_addr)})")
                            else:
                                write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Cluster full, cannot accept child {child_gui}")
                        else:
                            parent_info = self.neighbors_table.get(self.parent_gui)
                            if parent_info:
                                parent_addr = parent_info.get('ch_addr') or parent_info.get('addr')
                                if parent_addr:
                                    forward_pck = pck.copy()
                                    forward_pck['source'] = self.addr
                                    forward_pck['gui'] = pck['gui']
                                    forward_pck['forwarded_by'] = self.id
                                    self.route_and_forward_package(forward_pck)
                                    write_log(self, f"[JOIN] Node {self.id}: Forwarding JOIN_REQUEST from {pck['gui']} to parent {self.parent_gui}")
                                    return
                                else:
                                    temp_cluster_id = (self.id % (config.NUM_OF_CLUSTERS - 1)) + 1

                                    existing_ch, existing_ch_gui = self._check_existing_ch_in_cluster(temp_cluster_id)
                                    if existing_ch:
                                        existing_ch_info = self.neighbors_table.get(existing_ch_gui)
                                        if existing_ch_info:
                                            existing_ch_addr = existing_ch_info.get('ch_addr') or existing_ch_info.get('addr')
                                            if existing_ch_addr:
                                                forward_pck = pck.copy()
                                                forward_pck['source'] = self.addr
                                                forward_pck['gui'] = pck['gui']
                                                forward_pck['dest'] = existing_ch_addr
                                                self.route_and_forward_package(forward_pck)
                                                write_log(self, f"[CH_CREATION] Node {self.id}: CH {existing_ch_gui} exists with cluster {temp_cluster_id}, forwarding JOIN_REQUEST")
                                                return

                                    write_log(self, f"[CH_CREATION] Node {self.id}: Parent {self.parent_gui} has no address, becoming CH as fallback")
                                    self.ch_addr = wsn.Addr(temp_cluster_id, 254)
                                    self.set_role(Roles.CLUSTER_HEAD, reason="parent has no address - fallback CH")
                                    self._init_address_pool()
                                    self.send_heart_beat()
                                    if not hasattr(self, 'heartbeat_timer_active') or not self.heartbeat_timer_active:
                                        self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                                        self.heartbeat_timer_active = True
                                    if config.ENABLE_MULTIHOP_DISCOVERY:
                                        self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)
                                    self.send_network_request()
                                    child_gui = pck['gui']
                                    child_addr = self._assign_child_address(child_gui)
                                    if child_addr is not None:
                                        self.send_join_reply(child_gui, child_addr)
                                        write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Sent JOIN_REPLY to child {child_gui} (addr={format_addr(child_addr)})")
                                    else:
                                        write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Cluster full, cannot accept child {child_gui}")
                                    return
                            else:
                                temp_cluster_id = (self.id % (config.NUM_OF_CLUSTERS - 1)) + 1

                                existing_ch, existing_ch_gui = self._check_existing_ch_in_cluster(temp_cluster_id)
                                if existing_ch:
                                    existing_ch_info = self.neighbors_table.get(existing_ch_gui)
                                    if existing_ch_info:
                                        existing_ch_addr = existing_ch_info.get('ch_addr') or existing_ch_info.get('addr')
                                        if existing_ch_addr:
                                            forward_pck = pck.copy()
                                            forward_pck['source'] = self.addr
                                            forward_pck['gui'] = pck['gui']
                                            forward_pck['dest'] = existing_ch_addr
                                            self.route_and_forward_package(forward_pck)
                                            write_log(self, f"[CH_CREATION] Node {self.id}: CH {existing_ch_gui} exists with cluster {temp_cluster_id}, forwarding JOIN_REQUEST")
                                            return

                                write_log(self, f"[CH_CREATION] Node {self.id}: Parent {self.parent_gui} not in neighbors_table, becoming CH as fallback")
                                self.ch_addr = wsn.Addr(temp_cluster_id, 254)
                                self.set_role(Roles.CLUSTER_HEAD, reason="parent not in neighbors_table - fallback CH")
                                self._init_address_pool()
                                self.send_heart_beat()
                                if not hasattr(self, 'heartbeat_timer_active') or not self.heartbeat_timer_active:
                                    self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                                    self.heartbeat_timer_active = True
                                if config.ENABLE_MULTIHOP_DISCOVERY:
                                    self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)
                                self.send_network_request()
                                child_gui = pck['gui']
                                child_addr = self._assign_child_address(child_gui)
                                if child_addr is not None:
                                    self.send_join_reply(child_gui, child_addr)
                                    write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Sent JOIN_REPLY to child {child_gui} (addr={format_addr(child_addr)})")
                                else:
                                    write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Cluster full, cannot accept child {child_gui}")
                                return
            if pck['type'] == 'TRIGGER_CH_CREATION':
                target_gui = pck.get('target_gui')
                sender_gui = pck.get('gui')
                
                # Track CH creation requests for emergency connectivity
                if not hasattr(self, 'ch_creation_requests'):
                    self.ch_creation_requests = {}
                
                if sender_gui not in self.ch_creation_requests:
                    self.ch_creation_requests[sender_gui] = 0
                self.ch_creation_requests[sender_gui] += 1
                
                # More aggressive response for isolated nodes (multiple requests)
                should_become_ch = (target_gui is None or target_gui == self.id) and self.ch_addr is None
                
                # Emergency mode: become CH if we've received multiple requests from same isolated node
                if (not should_become_ch and 
                    self.role == Roles.REGISTERED and 
                    self.ch_creation_requests[sender_gui] >= 3):
                    should_become_ch = True
                    write_log(self, f"[CH_CREATION] Node {self.id}: EMERGENCY MODE - becoming CH due to {self.ch_creation_requests[sender_gui]} requests from isolated node {sender_gui}")
                
                if should_become_ch:
                    temp_cluster_id = (self.id % (config.NUM_OF_CLUSTERS - 1)) + 1

                    existing_ch, existing_ch_gui = self._check_existing_ch_in_cluster(temp_cluster_id)
                    if existing_ch:
                        write_log(self, f"[CH_CREATION] Node {self.id}: CH {existing_ch_gui} already exists with cluster {temp_cluster_id}, not creating duplicate")
                        return

                    write_log(self, f"[CH_CREATION] Node {self.id}: Received TRIGGER_CH_CREATION from {sender_gui}, becoming cluster head to help UNREGISTERED nodes")
                    self.ch_addr = wsn.Addr(temp_cluster_id, 254)
                    self.set_role(Roles.CLUSTER_HEAD, reason="TRIGGER_CH_CREATION from UNREGISTERED node")
                    self._init_address_pool()

                    self.send_heart_beat()
                    if not hasattr(self, 'heartbeat_timer_active') or not self.heartbeat_timer_active:
                        self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                        self.heartbeat_timer_active = True

                    if config.ENABLE_MULTIHOP_DISCOVERY:
                        self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)

                        self.send_network_request()
                    else:
                        if config.ENABLE_CLUSTER_DEBUG:
                            self.log(f"[CH_CREATION] Node {self.id}: Ignored TRIGGER_CH_CREATION - already CH (ch_addr={format_addr(self.ch_addr)})")
            if pck['type'] == 'NETWORK_REPLY':
                if self.ch_addr is not None:
                    old_ch_addr = self.ch_addr
                    self.ch_addr = pck['addr']
                    write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Updated cluster address from {format_addr(old_ch_addr)} to {format_addr(self.ch_addr)} (ROOT's official assignment)")
                    for node_addr, child_gui in list(self.node_addr_pool.items()):
                        if child_gui is not None:
                            new_child_addr = wsn.Addr(self.ch_addr.net_addr, node_addr)
                            self.send_join_reply(child_gui, new_child_addr)
                            write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Resent JOIN_REPLY to child {child_gui} with updated address {format_addr(new_child_addr)}")
                    return

                self.members_table = []
                self.ch_addr = pck['addr']

                if not config.USE_GLOBAL_TX_POWER:
                    cluster_id = self.ch_addr.net_addr
                    if cluster_id not in CLUSTER_TX_POWER:
                        if config.ENABLE_ENERGY_DEBUG:
                            msg = f"[ENERGY] Node {self.id}: Assigning initial TX power {config.TX_POWER_DEFAULT}dBm to cluster {cluster_id}"
                            self.log(msg)
                            write_log(self, msg)
                        set_cluster_tx_power(cluster_id, config.TX_POWER_DEFAULT)
                    self.update_cluster_tx_power()
                elif config.ENABLE_ENERGY_DEBUG:
                    msg = f"[ENERGY] Node {self.id}: Using global TX power {config.TX_POWER_DEFAULT}dBm (cluster {self.ch_addr.net_addr})"
                    self.log(msg)
                    write_log(self, msg)

                self.set_role(Roles.CLUSTER_HEAD)
                try:
                    write_clusterhead_distances_csv("clusterhead_distances.csv")
                except Exception as e:
                    self.log(f"CH CSV export error: {e}")

                self._init_address_pool()

                self.send_network_update()
                self.send_heart_beat()
                if config.ENABLE_MULTIHOP_DISCOVERY:
                    self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)

                write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Processing {len(self.received_JR_guis)} pending join requests")
                accepted_count = 0
                rejected_count = 0

                for gui in self.received_JR_guis:
                    child_already_assigned = any(assigned_gui == gui for assigned_gui in self.node_addr_pool.values())
                    if child_already_assigned:
                        if config.ENABLE_CLUSTER_DEBUG:
                            self.log(f"[CLUSTER_SIZE] Node {self.id}: Skipping pending child {gui} - already assigned")
                        continue

                    current_children = sum(1 for assigned_gui in self.node_addr_pool.values()
                                         if assigned_gui is not None)

                    if current_children >= config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER:
                        rejected_count += 1
                        self.debug_log(config.ENABLE_CLUSTER_DEBUG,
                                     f"[CLUSTER_SIZE] Node {self.id}: REJECTED pending child {gui} - cluster full "
                                     f"({current_children}/{config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER})")
                    else:
                        child_addr = self._assign_child_address(gui)
                        if child_addr is not None:
                            self.send_join_reply(gui, child_addr)
                            accepted_count += 1
                        else:
                            rejected_count += 1

                if rejected_count > 0:
                    self.log(f"[CLUSTER_SIZE] Node {self.id}: Processed pending requests - accepted={accepted_count}, rejected={rejected_count} (cluster full)")
                else:
                    self.log(f"[CLUSTER_SIZE] Node {self.id}: Processed pending requests - accepted={accepted_count}")
                self.received_JR_guis = []
            if pck['type'] == 'CH_TRANSFER':
                if self.id != ROOT_ID and self.role == Roles.REGISTERED:
                    new_ch_addr = pck.get('new_ch_addr') or pck.get('prev_ch_addr')
                    if new_ch_addr is not None:
                        self.log(f"[CH_TRANSFER] Node {self.id} accepting CH role transfer from {pck.get('gui')}")
                        write_log(self, f"[CH_TRANSFER] Node {self.id} accepting CH role from {pck.get('gui')}")

                        self.set_role(Roles.CLUSTER_HEAD, reason="received CH transfer")
                        self.ch_addr = new_ch_addr

                        if hasattr(self, '_init_address_pool'):
                            self._init_address_pool()

                        self.send_network_update()
                        self.send_heart_beat()
                        self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)

                        if getattr(config, 'ENABLE_MULTIHOP_DISCOVERY', False):
                            self.set_timer('TIMER_NEIGHBOR_SHARE', getattr(config, 'NEIGHBOR_SHARE_INTERVAL', 30))

                        ack_pck = {
                            'dest': pck.get('source'),
                            'type': 'CH_TRANSFER_ACK',
                            'source': self.addr,
                            'gui': self.id,
                            'new_ch_addr': self.ch_addr
                        }
                        self.route_and_forward_package(ack_pck)
                        write_log(self, f"[CH_TRANSFER] Node {self.id} sent CH_TRANSFER_ACK to {format_addr(ack_pck['dest'])}")
                return

        elif self.role == Roles.UNDISCOVERED:
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
                self.kill_timer('TIMER_PROBE')
                self.become_unregistered()

        if self.role == Roles.UNREGISTERED:
            if pck['type'] == 'HEART_BEAT':
                sender_gui = pck.get('gui')
                sender_role = pck.get('role')
                sender_addr = pck.get('addr') or pck.get('source') or pck.get('ch_addr')
                if len(self.candidate_parents_table) == 0:
                    write_log(self, f"[JOIN] Node {self.id}: Received HEART_BEAT from {sender_gui} (role={sender_role}, addr={format_addr(sender_addr)})")
                self.update_neighbor(pck)
            if pck['type'] == 'NEIGHBOR_SHARE':
                self.process_neighbor_share(pck)
            if pck['type'] == 'JOIN_REPLY':
                if pck['dest_gui'] == self.id:
                    sender_gui = pck.get('gui')
                    sender_node = self._find_node_by_gui(sender_gui)
                    if sender_node and sender_node.role not in (Roles.CLUSTER_HEAD, Roles.ROOT):
                        if config.ENABLE_CLUSTER_DEBUG:
                            self.log(f"[JOIN] Node {self.id}: Rejecting JOIN_REPLY from {sender_gui} (invalid role: {sender_node.role})")
                            write_log(self, f"[JOIN] Node {self.id}: Rejecting JOIN_REPLY from {sender_gui} (role={sender_node.role}, must be CH or ROOT)")
                        return

                    self.addr = pck['addr']
                    self.parent_gui = sender_gui
                    self.root_addr = pck['root_addr']
                    self.hop_count = pck['hop_count']
                    self.registered_time = self.now
                    if self.wake_up_time is not None:
                        log_registration_time(self.id, self.wake_up_time, self.registered_time)
                    self.draw_parent()
                    self.kill_timer('TIMER_JOIN_REQUEST')

                    if self.addr is not None:
                        self.update_cluster_tx_power()

                    self.send_heart_beat()
                    self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                    self.send_join_ack(pck['source'])
                    if self.ch_addr is not None:
                        self.set_role(Roles.CLUSTER_HEAD)
                        self.send_network_update()
                    else:
                        self.set_role(Roles.REGISTERED)
                        self.registered_since = self.now
                        if config.ENABLE_MULTIHOP_DISCOVERY:
                            self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)
                        self.set_timer('TIMER_SENSOR', max(1, config.DATA_PACKET_INTERVAL))
                        if getattr(config, 'ENABLE_PROACTIVE_CH_CREATION', True):
                            proactive_timer = getattr(config, 'PROACTIVE_CH_TIMER', 60)
                            self.set_timer('TIMER_PROACTIVE_CH', proactive_timer)

                    if config.ENABLE_ENERGY_MODEL:
                        self.set_timer('TIMER_BASELINE_ENERGY', 1.0)
                        self.set_timer('TIMER_POWER_LOG', 100.0)
            if pck['type'] == 'CH_TRANSFER':
                if self.id != ROOT_ID and self.role == Roles.REGISTERED:
                    new_ch_addr = pck.get('new_ch_addr') or pck.get('prev_ch_addr')
                    if new_ch_addr is not None:
                        self.log(f"[CH_TRANSFER] Node {self.id} accepting CH role transfer from {pck.get('gui')}")
                        write_log(self, f"[CH_TRANSFER] Node {self.id} accepting CH role from {pck.get('gui')}")

                        self.set_role(Roles.CLUSTER_HEAD, reason="received CH transfer")
                        self.ch_addr = new_ch_addr

                        if hasattr(self, '_init_address_pool'):
                            self._init_address_pool()

                        self.send_network_update()
                        self.send_heart_beat()
                        self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)

                        if getattr(config, 'ENABLE_MULTIHOP_DISCOVERY', False):
                            self.set_timer('TIMER_NEIGHBOR_SHARE', getattr(config, 'NEIGHBOR_SHARE_INTERVAL', 30))

                        ack_pck = {
                            'dest': pck.get('source'),
                            'type': 'CH_TRANSFER_ACK',
                            'source': self.addr,
                            'gui': self.id,
                            'new_ch_addr': self.ch_addr
                        }
                        self.route_and_forward_package(ack_pck)
                        write_log(self, f"[CH_TRANSFER] Node {self.id} sent CH_TRANSFER_ACK to {format_addr(ack_pck['dest'])}")
                return

        elif self.role == Roles.ROUTER:
            dest = pck.get('dest')

            is_broadcast = False
            if dest is not None and hasattr(dest, 'is_equal'):
                is_broadcast = dest.is_equal(wsn.BROADCAST_ADDR)
            is_for_self = addr_equals(dest, self.addr) or addr_equals(dest, self.ch_addr)

            if not is_broadcast and not is_for_self:
                if 'next_hop' in pck.keys():
                    self.route_and_forward_package(pck)
                    return
                else:
                    self.route_and_forward_package(pck)
                    return

            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'NEIGHBOR_SHARE':
                self.process_neighbor_share(pck)
            if pck['type'] == 'PROBE':
                self.send_heart_beat()

            if pck['type'] == 'NETWORK_UPDATE':
                self.child_networks_table[pck['gui']] = pck['child_networks']

    def on_timer_fired(self, name, *args, **kwargs):
        if name == 'TIMER_ARRIVAL':
            self.scene.nodecolor(self.id, 1, 0, 0)
            self.wake_up()
            self.wake_up_time = self.now
            self.set_timer('TIMER_PROBE', 1)

        elif name == 'TIMER_PROBE':
            if self.c_probe < self.th_probe:
                self.send_probe()
                self.c_probe += 1
                self.set_timer('TIMER_PROBE', 1)
            else:
                if self.is_root_eligible:
                    self.members_table = []
                    self.addr = wsn.Addr(0, 254)
                    self.ch_addr = wsn.Addr(0, 254)
                    self.root_addr = self.addr
                    self.hop_count = 0
                    self.set_role(Roles.ROOT)

                    self._init_address_pool()
                    self.cluster_addr_pool = {i: None for i in range(1, config.NUM_OF_CLUSTERS + 1)}
                    self.log(f"[CLUSTER_SIZE] ROOT Node {self.id}: Initialized pools - {config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER} child slots, {config.NUM_OF_CLUSTERS} cluster IDs (ROOT uses net_addr=0)")

                    self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                    if config.ENABLE_MULTIHOP_DISCOVERY:
                        self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)

                    if config.ENABLE_CLUSTER_OPTIMIZATION:
                        self.set_timer('TIMER_CLUSTER_OPTIMIZATION', config.CLUSTER_OPTIMIZATION_INTERVAL)

                    if config.ENABLE_ENERGY_MODEL:
                        self.set_timer('TIMER_BASELINE_ENERGY', 1.0)
                else:
                    if self.role == Roles.UNDISCOVERED and len(self.neighbors_table) == 0:
                        if self.now > 30:
                            self.become_unregistered()
                    self.c_probe = 0
                    self.set_timer('TIMER_PROBE', 30)
                    if self.role in (Roles.UNDISCOVERED, Roles.UNREGISTERED):
                        self.set_timer('TIMER_JOIN_REQUEST', 20)

        elif name == 'TIMER_HEART_BEAT':
            self.send_heart_beat()
            self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
            if self.role == Roles.ROUTER:
                self.heartbeat_timer_active = True
        elif name == 'TIMER_BASELINE_ENERGY':
            if config.ENABLE_ENERGY_MODEL and not self.is_shutdown:
                baseline_power = config.CC2420_VOLTAGE * config.BASELINE_CURRENT
                baseline_energy = baseline_power * 1.0

                if self.energy_remaining >= baseline_energy:
                    self.energy_remaining -= baseline_energy
                    self.energy_baseline_total += baseline_energy

                    if config.ENABLE_ENERGY_DEBUG and int(self.now) % 10 == 0:
                        energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
                        msg = f"[ENERGY] Node {self.id}: Baseline - {baseline_energy*1e6:.3f}µJ, remaining={self.energy_remaining:.6f}J ({energy_percent:.2f}%)"
                        self.log(msg)
                        write_log(self, msg)
                else:
                    self.energy_remaining = 0.0
                    self.shutdown_node("Insufficient energy for baseline operation")
                    return

                self.check_energy_level()

                if config.ENABLE_ENERGY_DEBUG:
                    energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
                    if energy_percent < 10.0 and energy_percent >= (config.BATTERY_ENERGY_MIN / config.BATTERY_ENERGY_TOTAL * 100):
                        if int(self.now) % 5 == 0:
                            msg = f"[ENERGY] Node {self.id}: WARNING - Low energy: {self.energy_remaining:.6f}J ({energy_percent:.2f}%)"
                            self.log(msg)
                            write_log(self, msg)

                self.set_timer('TIMER_BASELINE_ENERGY', 1.0)

        elif name == 'TIMER_NEIGHBOR_SHARE':
            if config.ENABLE_MULTIHOP_DISCOVERY:
                self.share_neighbor_info()
                self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)

        elif name == 'TIMER_JOIN_REQUEST':
            if len(self.candidate_parents_table) == 0:
                self.send_probe()
                self.failed_join_attempts += 1
                
                # Update TX power after failed attempts (adaptive boost)
                self.update_cluster_tx_power()

                if config.ENABLE_CLUSTER_DEBUG and self.failed_join_attempts % 10 == 0:
                    total_neighbors = len(self.neighbors_table)
                    valid_parents = sum(1 for n in self.neighbors_table.values()
                                      if n.get('role') in (Roles.CLUSTER_HEAD, Roles.ROUTER, Roles.ROOT))
                    self.log(f"[JOIN] Node {self.id}: No candidates - total neighbors={total_neighbors}, valid parents={valid_parents}, failed attempts={self.failed_join_attempts}")

                threshold = getattr(config, 'UNREGISTERED_CH_TRIGGER_THRESHOLD', 3)
                if self.failed_join_attempts >= threshold and (self.failed_join_attempts % threshold == 0):
                    self.log(f"[CH_CREATION] Node {self.id}: {self.failed_join_attempts} failed attempts - triggering CH creation")
                    self._trigger_ch_creation()

                self.set_timer('TIMER_JOIN_REQUEST', 20)
                if config.ENABLE_CLUSTER_DEBUG and self.failed_join_attempts % 5 == 0:
                    self.log(f"[JOIN] Node {self.id}: No candidates, retrying probe and join request (failed attempts={self.failed_join_attempts})")
            else:
                if self.role not in (Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROUTER, Roles.ROOT):
                    if self.last_join_request_sent_time is not None:
                        time_since_last = self.now - self.last_join_request_sent_time
                        if time_since_last < (self.join_request_cooldown - 0.0001):
                            remaining_cooldown = self.join_request_cooldown - time_since_last
                            if remaining_cooldown < 0.0001:
                                remaining_cooldown = 0.0001
                            self.set_timer('TIMER_JOIN_REQUEST', remaining_cooldown)
                            if config.ENABLE_CLUSTER_DEBUG:
                                write_log(self, f"[JOIN] Node {self.id}: Rate limiting JOIN_REQUEST (last sent {time_since_last:.1f}s ago, rescheduling in {remaining_cooldown:.1f}s)")
                            return

                    time_before = self.last_join_request_sent_time
                    self.select_and_join()
                    if self.last_join_request_sent_time is not None and self.last_join_request_sent_time != time_before:
                        self.set_timer('TIMER_JOIN_REQUEST', self.join_request_cooldown)
                    else:
                        self.set_timer('TIMER_JOIN_REQUEST', 20)
                else:
                    self.set_timer('TIMER_JOIN_REQUEST', 60)

        elif name == 'TIMER_CH_TRANSFER_DELAY':
            if self.role == Roles.CLUSTER_HEAD and self.ch_transfer_enabled and self.id != ROOT_ID:
                if config.ENABLE_CLUSTER_DEBUG:
                    self.log(f"[CH_TRANSFER] Node {self.id}: TIMER_CH_TRANSFER_DELAY fired, initiating transfer (members={len(self.members_table)})")
                self.initiate_ch_transfer()
            else:
                if config.ENABLE_CLUSTER_DEBUG:
                    self.log(f"[CH_TRANSFER] Node {self.id}: TIMER_CH_TRANSFER_DELAY fired but conditions not met (role={self.role}, enabled={self.ch_transfer_enabled}, is_root={self.id == ROOT_ID})")
        elif name == 'TIMER_PROACTIVE_CH':
            proactive_timer = getattr(config, 'PROACTIVE_CH_TIMER', 60)
            if self.role == Roles.REGISTERED and getattr(config, 'ENABLE_PROACTIVE_CH_CREATION', True):
                if len(self.received_JR_guis) == 0 and self.ch_addr is None and self.parent_gui is None:
                    self.log(f"[CH_CREATION] Node {self.id}: Proactive CH creation - isolated REGISTERED node (no parent, no JOIN_REQUEST) after {proactive_timer}s, becoming cluster head")
                    self.send_network_request()
                else:
                    if config.ENABLE_CLUSTER_DEBUG:
                        reason = []
                        if len(self.received_JR_guis) > 0:
                            reason.append(f"has {len(self.received_JR_guis)} JOIN_REQUESTs")
                        if self.ch_addr is not None:
                            reason.append("already CH")
                        if self.parent_gui is not None:
                            reason.append(f"has parent {self.parent_gui}")
                        self.log(f"[CH_CREATION] Node {self.id}: Proactive CH timer fired but skipped ({', '.join(reason)})")
            self.set_timer('TIMER_PROACTIVE_CH', proactive_timer)

        elif name == 'TIMER_CLUSTER_OPTIMIZATION':
            if self.role == Roles.ROOT and config.ENABLE_CLUSTER_OPTIMIZATION:
                optimize_clusters()
                self.set_timer('TIMER_CLUSTER_OPTIMIZATION', config.CLUSTER_OPTIMIZATION_INTERVAL)

        elif name == 'TIMER_SENSOR':
            self.send_random_data_packet()
            interval = max(1, config.DATA_PACKET_INTERVAL)
            self.set_timer('TIMER_SENSOR', interval)
        elif name == 'TIMER_EXPORT_CH_CSV':
            if self.role == Roles.ROOT:
                write_clusterhead_distances_csv("clusterhead_distances.csv")
                self.set_timer('TIMER_EXPORT_CH_CSV', config.EXPORT_CH_CSV_INTERVAL)
        elif name == 'TIMER_EXPORT_NEIGHBOR_CSV':
            if self.role == Roles.ROOT:
                write_neighbor_distances_csv("neighbor_distances.csv")
                self.set_timer('TIMER_EXPORT_NEIGHBOR_CSV', config.EXPORT_NEIGHBOR_CSV_INTERVAL)
        elif name == 'TIMER_PERIODIC_SNAPSHOT':
            if self.role == Roles.ROOT and config.ENABLE_NETWORK_SNAPSHOTS:
                take_network_snapshot(f"Periodic_{self.now:.0f}s", self.now)
                interval = getattr(config, 'SNAPSHOT_PERIODIC_INTERVAL', 100)
                self.set_timer('TIMER_PERIODIC_SNAPSHOT', interval)
        elif name == 'TIMER_POWER_LOG':
            if config.ENABLE_ENERGY_MODEL and hasattr(self, 'energy_remaining'):
                log_power_level(self.id, self.now, self.energy_remaining)
                self.set_timer('TIMER_POWER_LOG', 100.0)
        
        elif name == 'TIMER_CONNECTIVITY_CHECK':
            if self.role == Roles.ROOT and config.ENABLE_ENERGY_MODEL:
                lifetime_reached = check_and_log_connectivity(self.now)
                if not lifetime_reached:
                    # Continue checking if lifetime not reached yet
                    self.set_timer('TIMER_CONNECTIVITY_CHECK', CONNECTIVITY_CHECK_INTERVAL)

        elif name.startswith('TIMER_NODE_FAILURE_'):
            debug_log(f"data_collection_tree.py:{3346}", "TIMER_NODE_FAILURE fired", {"node_id": self.id, "sim_time": self.sim.now, "timer_name": name}, "A")
            current_role = _role_name(self.role)
            log_to_console_and_file(f"[FAILURE_CHECK] Node {self.id}: Timer fired at {self.sim.now:.2f}s, current role: {current_role}")

            debug_log(f"data_collection_tree.py:{3353}", "Before fail_node() call", {"node_id": self.id, "role": current_role, "is_failed_before": self.is_failed, "FAILED_NODES_before": list(FAILED_NODES)}, "B")

            if self.role not in [Roles.REGISTERED, Roles.CLUSTER_HEAD]:
                retry_count = getattr(self, '_failure_retry_count', 0)
                max_retries = 10
                retry_delay = 5.0

                if retry_count < max_retries:
                    self._failure_retry_count = retry_count + 1
                    log_to_console_and_file(f"[FAILURE_RETRY] Node {self.id}: Not registered yet (role: {current_role}), rescheduling failure in {retry_delay}s (retry {retry_count + 1}/{max_retries})")
                    self.set_timer(f'TIMER_NODE_FAILURE_{self.id}', retry_delay)
                    return

            was_failed_before = self.is_failed
            self.fail_node()

            debug_log(f"data_collection_tree.py:{3356}", "After fail_node() call", {"node_id": self.id, "is_failed_after": self.is_failed, "was_failed_before": was_failed_before, "FAILED_NODES_after": list(FAILED_NODES)}, "C")

            if was_failed_before == self.is_failed and not self.is_failed:
                log_to_console_and_file(f"[FAILURE_SKIPPED] Node {self.id}: Failure skipped - node not REGISTERED/CLUSTER_HEAD (role: {current_role})")
                return
            elif self.is_failed:
                log_to_console_and_file(f"[FAILURE_SUCCESS] Node {self.id}: Successfully failed at {self.sim.now:.2f}s")

            debug_log(f"data_collection_tree.py:{3363}", "Before snapshot at T1", {"node_id": self.id, "FAILED_NODES": list(FAILED_NODES), "snapshot_enabled": config.ENABLE_NETWORK_SNAPSHOTS and config.SNAPSHOT_AT_T1}, "E")

            if config.ENABLE_NETWORK_SNAPSHOTS and config.SNAPSHOT_AT_T1 and self.is_failed:
                take_network_snapshot("At_T1_Failure", self.sim.now)

            for recovery_time, node_id, failure_time in SCHEDULED_RECOVERIES:
                if node_id == self.id:
                    recovery_delay = recovery_time - self.sim.now
                    self.set_timer(f'TIMER_NODE_RECOVERY_{self.id}', recovery_delay)

                    if config.ENABLE_NETWORK_SNAPSHOTS and config.SNAPSHOT_T2_T3_RECOVERY:
                        t2_t3_time = failure_time + (recovery_delay / 2)
                        t2_t3_delay = t2_t3_time - self.sim.now
                        if t2_t3_delay > 0:
                            self.set_timer('TIMER_SNAPSHOT_T2_T3', t2_t3_delay)
                    break

        elif name.startswith('TIMER_NODE_RECOVERY_'):
            self.recover_node()

            if config.ENABLE_NETWORK_SNAPSHOTS and config.SNAPSHOT_AFTER_T3_COUNT > 0:
                for i in range(1, config.SNAPSHOT_AFTER_T3_COUNT + 1):
                    delay = i * config.SNAPSHOT_AFTER_T3_INTERVAL
                    self.set_timer(f'TIMER_SNAPSHOT_AFTER_T3_{i}', delay)

        elif name == 'TIMER_SNAPSHOT_T1_T2':
            if config.ENABLE_NETWORK_SNAPSHOTS:
                take_network_snapshot("T1-T2_After_Failure", self.sim.now)

        elif name == 'TIMER_SNAPSHOT_T2_T3':
            if config.ENABLE_NETWORK_SNAPSHOTS:
                take_network_snapshot("T2-T3_Recovery_In_Progress", self.sim.now)

        elif name == 'TIMER_SNAPSHOT_BEFORE_T1':
            if config.ENABLE_NETWORK_SNAPSHOTS and config.SNAPSHOT_BEFORE_T1:
                take_network_snapshot("Before_T1_Baseline", self.sim.now)

        elif name.startswith('TIMER_SNAPSHOT_AFTER_T3_'):
            snapshot_num = name.split('_')[-1]
            if config.ENABLE_NETWORK_SNAPSHOTS:
                take_network_snapshot(f"After_T3_Stabilization_{snapshot_num}", self.sim.now)

        elif name == 'TIMER_FAILURE_HIGHLIGHT_END':
            if self.is_failed:
                self.scene.nodecolor(self.id, 0.5, 0.5, 0.5)

        elif name == 'TIMER_ORPHAN_HIGHLIGHT_END':
            if self.id in ORPHANED_NODES and not self.is_failed:
                if self.role == Roles.UNREGISTERED:
                    self.scene.nodecolor(self.id, 1, 1, 0)
                elif self.role == Roles.REGISTERED:
                    self.scene.nodecolor(self.id, 0, 1, 0)
                else:
                    self.scene.nodecolor(self.id, 1, 1, 1)

ROOT_ID = 1

def write_node_distances_csv(path="node_distances.csv"):
    # Write pairwise node-to-node Euclidean distances as an edge list.
    ids = sorted(NODE_POS.keys())
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "target_id", "distance"])
        for i, sid in enumerate(ids):
            x1, y1 = NODE_POS[sid]
            for tid in ids[i+1:]:
                x2, y2 = NODE_POS[tid]
                dist = math.hypot(x1 - x2, y1 - y2)
                w.writerow([sid, tid, f"{dist:.6f}"])

def write_node_distance_matrix_csv(path="node_distance_matrix.csv"):
    ids = sorted(NODE_POS.keys())
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node_id"] + ids)
        for sid in ids:
            x1, y1 = NODE_POS[sid]
            row = [sid]
            for tid in ids:
                x2, y2 = NODE_POS[tid]
                dist = math.hypot(x1 - x2, y1 - y2)
                row.append(f"{dist:.6f}")
            w.writerow(row)

def write_clusterhead_distances_csv(path="clusterhead_distances.csv"):
    # Write pairwise distances between current cluster heads.
    clusterheads = []
    for node in sim.nodes:
        if hasattr(node, "role") and node.role == Roles.CLUSTER_HEAD and node.id in NODE_POS:
            x, y = NODE_POS[node.id]
            clusterheads.append((node.id, x, y))

    if len(clusterheads) < 2:
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(["clusterhead_1", "clusterhead_2", "distance"])
        return

    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["clusterhead_1", "clusterhead_2", "distance"])
        for i, (id1, x1, y1) in enumerate(clusterheads):
            for id2, x2, y2 in clusterheads[i+1:]:
                dist = math.hypot(x1 - x2, y1 - y2)
                w.writerow([id1, id2, f"{dist:.6f}"])

def write_neighbor_distances_csv(path="neighbor_distances.csv", dedupe_undirected=True):
    if not globals().get("NODE_POS"):
        raise RuntimeError("NODE_POS is missing; record positions during create_network().")

    seen_pairs = set()
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "neighbor_id", "distance",
                    "neighbor_role", "neighbor_hop_count", "arrival_time"])

        for node in sim.nodes:
            if not hasattr(node, "neighbors_table"):
                continue

            x1, y1 = NODE_POS.get(node.id, (None, None))
            if x1 is None:
                continue

            for n_gui, pck in getattr(node, "neighbors_table", {}).items():
                if dedupe_undirected:
                    key = (min(node.id, n_gui), max(node.id, n_gui))
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)

                x2, y2 = NODE_POS.get(n_gui, (None, None))
                if x2 is None:
                    continue

                dist = pck.get("distance")
                if dist is None:
                    dist = math.hypot(x1 - x2, y1 - y2)

                n_role = getattr(pck.get("role", None), "name", pck.get("role", None))
                hop = pck.get("hop_count", "")
                at  = pck.get("arrival_time", "")

                w.writerow([node.id, n_gui, f"{dist:.6f}", n_role, hop, at])

def write_multihop_neighbor_table_csv(path="multihop_neighbor_table.csv"):
    # Export multihop neighbor table for all nodes
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "neighbor_id", "hop_distance", "next_hop", "euclidean_distance"])

        for node in sim.nodes:
            if not hasattr(node, "multihop_neighbor_table"):
                continue

            for neighbor_gui, info in node.multihop_neighbor_table.items():
                w.writerow([
                    node.id,
                    neighbor_gui,
                    info['hop_dist'],
                    info['next_hop'],
                    f"{info['distance']:.6f}"
                ])

    log_to_console_and_file(f"Exported multihop neighbor table to {path}")


def write_cluster_members_csv(path="cluster_members.csv"):
    """Export cluster membership information for all cluster heads."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cluster_head_id", "cluster_head_addr", "member_node_id", "member_addr", "cluster_size", "timestamp"])

        current_time = sim.now if hasattr(sim, 'now') else 0
        
        for node in sim.nodes:
            # Only export data for cluster heads that have members
            if (hasattr(node, 'role') and node.role == Roles.CLUSTER_HEAD and 
                hasattr(node, 'members_table') and len(node.members_table) > 0):
                
                cluster_size = len(node.members_table)
                ch_addr = format_addr(node.addr) if hasattr(node, 'addr') and node.addr else "None"
                
                for member_addr in node.members_table:
                    # Find the member node to get its ID
                    member_node = node._find_node_by_addr(member_addr)
                    member_id = member_node.id if member_node else "Unknown"
                    
                    w.writerow([
                        node.id,
                        ch_addr,
                        member_id,
                        format_addr(member_addr),
                        cluster_size,
                        f"{current_time:.3f}"
                    ])

    log_to_console_and_file(f"Exported cluster members table to {path}")


def generate_power_analysis_csvs():
    """Generate power analysis CSV files similar to friend's approach."""
    try:
        from collections import defaultdict
        
        input_file = "node_power_levels_over_time.csv"
        if not Path(input_file).exists():
            log_to_console_and_file("⚠️  No power data found for analysis")
            return
        
        log_to_console_and_file("📊 Generating power analysis CSV files...")
        
        # Read and aggregate power data
        power_by_time = defaultdict(list)
        node_latest_power = {}
        node_data = []
        node_initial_power = {}
        
        with open(input_file, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    node_id = int(row["node_id"])
                    power = float(row["power"])
                    time = float(row["time"])
                    
                    # For time-based aggregation
                    t_int = int(time)
                    if power <= 90000:  # Filter invalid values
                        power_by_time[t_int].append(power)
                    
                    # For latest power levels
                    if node_id not in node_latest_power or time > node_latest_power[node_id]["time"]:
                        node_latest_power[node_id] = {"power": power, "time": time}
                    
                    # For detailed progression
                    if node_id not in node_initial_power:
                        node_initial_power[node_id] = power
                    node_data.append((node_id, time, power))
                    
                except (ValueError, KeyError):
                    continue
        
        if not power_by_time:
            log_to_console_and_file("⚠️  No valid power data found")
            return
        
        # 1. averagePower_by_time.csv
        times = sorted(power_by_time.keys())
        with open("averagePower_by_time.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["time", "avg_power", "min_power", "max_power", "num_nodes"])
            writer.writeheader()
            for t in times:
                values = power_by_time[t]
                if values:
                    writer.writerow({
                        "time": t,
                        "avg_power": sum(values) / len(values),
                        "min_power": min(values),
                        "max_power": max(values),
                        "num_nodes": len(values)
                    })
        
        # 2. NodePower_levels.csv
        with open("NodePower_levels.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["node_id", "current_power", "last_update_time"])
            writer.writeheader()
            for node_id in sorted(node_latest_power.keys()):
                data = node_latest_power[node_id]
                writer.writerow({
                    "node_id": node_id,
                    "current_power": data["power"],
                    "last_update_time": data["time"]
                })
        
        # 3. nodePower_over_time.csv
        node_data.sort(key=lambda x: (x[0], x[1]))  # Sort by node_id, then time
        with open("nodePower_over_time.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["node_id", "time", "power", "power_consumed", "power_percentage"])
            writer.writeheader()
            for node_id, time, power in node_data:
                initial = node_initial_power[node_id]
                consumed = initial - power
                percentage = (power / initial * 100) if initial > 0 else 0
                writer.writerow({
                    "node_id": node_id,
                    "time": time,
                    "power": power,
                    "power_consumed": consumed,
                    "power_percentage": percentage
                })
        
        log_to_console_and_file("✓ Power analysis CSV files generated:")
        log_to_console_and_file("  - averagePower_by_time.csv (time-based averages)")
        log_to_console_and_file("  - NodePower_levels.csv (current node power levels)")
        log_to_console_and_file("  - nodePower_over_time.csv (detailed power progression)")
        
    except Exception as e:
        log_to_console_and_file(f"⚠️  Error generating power analysis: {e}")


def create_network(node_class, number_of_nodes=100):
    edge = math.ceil(math.sqrt(number_of_nodes))
    for i in range(number_of_nodes):
        x = i / edge
        y = i % edge
        px = 300 + config.SCALE*x * config.SIM_NODE_PLACING_CELL_SIZE + random.uniform(-1 * config.SIM_NODE_PLACING_CELL_SIZE / 3, config.SIM_NODE_PLACING_CELL_SIZE / 3)
        py = 200 + config.SCALE* y * config.SIM_NODE_PLACING_CELL_SIZE + random.uniform(-1 * config.SIM_NODE_PLACING_CELL_SIZE / 3, config.SIM_NODE_PLACING_CELL_SIZE / 3)
        node = sim.add_node(node_class, (px, py))
        NODE_POS[node.id] = (px, py)
        ALL_NODES.append(node)
        node.tx_range = config.NODE_TX_RANGE * config.SCALE
        node.logging = True
        node.arrival = random.uniform(0, config.NODE_ARRIVAL_MAX)
        if node.id == ROOT_ID:
            node.arrival = 0.1

init_log_file()

random.seed(getattr(config, 'SIM_SEED', 42))
log_to_console_and_file(f" Using random seed: {getattr(config, 'SIM_SEED', 42)}")

sim = wsn.Simulator(
    duration=config.SIM_DURATION,
    timescale=config.SIM_TIME_SCALE,
    visual=config.SIM_VISUALIZATION,
    terrain_size=config.SIM_TERRAIN_SIZE,
    title=config.SIM_TITLE,
    seed=getattr(config, 'SIM_SEED', 42))

create_network(SensorNode, config.SIM_NODE_COUNT)

write_node_distances_csv("node_distances.csv")
write_node_distance_matrix_csv("node_distance_matrix.csv")

if config.ENABLE_NODE_FAILURE_RECOVERY:
    eligible_nodes = [n for n in ALL_NODES if n.id != ROOT_ID]
    if len(eligible_nodes) >= config.NUM_NODES_TO_FAIL:
        selected_nodes = random.sample(eligible_nodes, config.NUM_NODES_TO_FAIL)
        for i, node in enumerate(selected_nodes):
            failure_time = config.NODE_FAILURE_START_TIME + i * config.NODE_FAILURE_INTERVAL
            recovery_time = failure_time + random.uniform(config.NODE_RECOVERY_TIME_MIN,
                                                          config.NODE_RECOVERY_TIME_MAX)
            SCHEDULED_FAILURES.append((failure_time, node.id))
            SCHEDULED_RECOVERIES.append((recovery_time, node.id, failure_time))

            node.set_timer(f'TIMER_NODE_FAILURE_{node.id}', failure_time)

            if i == 0 and config.ENABLE_NETWORK_SNAPSHOTS and config.SNAPSHOT_BEFORE_T1:
                before_t1_time = failure_time - 5.0
                if before_t1_time > 0:
                    node.set_timer('TIMER_SNAPSHOT_BEFORE_T1', before_t1_time)

            msg = f" Scheduled: Node {node.id} will fail at {failure_time:.1f}s, recover at {recovery_time:.1f}s (downtime: {recovery_time-failure_time:.1f}s)"
            log_to_console_and_file(msg)

sim.run()
log_to_console_and_file("Simulation Finished")

if config.ENABLE_NETWORK_SNAPSHOTS and config.SNAPSHOT_FINAL_STATE:
    take_network_snapshot("Final_State", sim.now)

if config.ENABLE_MULTIHOP_DISCOVERY:
    write_multihop_neighbor_table_csv("multihop_neighbor_table.csv")

# Export cluster membership information
write_cluster_members_csv("cluster_members.csv")

calculate_and_log_average_join_time()
calculate_and_log_average_packet_delay()
if config.ENABLE_NODE_FAILURE_RECOVERY:
    calculate_and_log_recovery_statistics()
log_packet_loss_statistics()

# Generate power analysis CSV files (friend's style)
if config.ENABLE_ENERGY_MODEL:
    generate_power_analysis_csvs()

copy_simulation_outputs()

close_log_file()
