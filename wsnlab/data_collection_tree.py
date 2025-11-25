import random
from enum import Enum
import sys
sys.path.insert(1, '.')
from source import wsnlab_vis as wsn
import math
from source import config
from collections import Counter
from datetime import datetime
import os


import csv  # <— add this near your other imports

# Track where each node is placed
NODE_POS = {}  # {node_id: (x, y)}

# logging + csv handles
LOG_FILE = None
LOG_FILE_NAME = None
PACKET_ROUTE_FILE = "packet_routes.csv"
PACKET_ROUTE_HEADER_WRITTEN = False
PACKET_DELAY_FILE = "packet_delays.csv"
REGISTRATION_LOG_FILE = "registration_log.csv"
PACKET_PATH_FILE = "packet_paths.csv"
DATA_PACKET_COUNTER = 0

# packet loss / channel stats
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
FAILED_NODES = set()  # Set of currently failed node IDs
ORPHANED_NODES = set()  # Set of currently orphaned node IDs
RECOVERY_EVENTS = []  # List of recovery events
SCHEDULED_FAILURES = []  # List of (time, node_id) tuples for scheduled failures
SCHEDULED_RECOVERIES = []  # List of (time, node_id, failure_time) tuples

# --- tracking containers ---
ALL_NODES = []              # node objects
CLUSTER_HEADS = []
ROLE_COUNTS = Counter()     # live tally per Roles enum

def _addr_str(a): return "" if a is None else str(a)
def _role_name(r): return r.name if hasattr(r, "name") else str(r)


def addr_key(addr):
    """Return hashable tuple for an address."""
    if addr is None:
        return None
    return (getattr(addr, 'net_addr', None), getattr(addr, 'node_addr', None))


def format_addr(addr):
    if addr is None:
        return "None"
    return f"[{addr.net_addr},{addr.node_addr}]"


def addr_equals(a, b):
    """Safe address comparison that tolerates None values."""
    if a is None or b is None:
        return False
    try:
        return a == b
    except AttributeError:
        return False


def next_packet_id():
    """Return a monotonically increasing packet identifier."""
    global DATA_PACKET_COUNTER
    DATA_PACKET_COUNTER += 1
    return DATA_PACKET_COUNTER


def init_log_file():
    """Create timestamped log file if enabled."""
    global LOG_FILE, LOG_FILE_NAME, PACKET_ROUTE_HEADER_WRITTEN
    if not config.ENABLE_LOG_FILE or LOG_FILE is not None:
        return None
    timestamp = datetime.now().strftime("%d-%m-%y-%H%M")
    LOG_FILE_NAME = f"wsn_log_{timestamp}.log"
    LOG_FILE = open(LOG_FILE_NAME, "w", buffering=1)
    # Don't use log_to_console_and_file here since LOG_FILE was just opened
    print(f"Logging to {LOG_FILE_NAME}")
    LOG_FILE.write(f"Logging to {LOG_FILE_NAME}\n")
    LOG_FILE.flush()
    # reset packet route file each run
    with open(PACKET_ROUTE_FILE, "w", newline="") as f:
        pass
    with open(PACKET_DELAY_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["packet_type", "source", "dest", "source_gui", "dest_gui",
                         "created_at", "delivered_at", "delay"])
    with open(REGISTRATION_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["node_id", "start_time", "registered_time", "join_delay"])
    with open(PACKET_PATH_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["packet_id", "packet_type", "source_gui", "dest_gui",
                         "path", "hop_count", "started_at", "delivered_at", "delay"])
    # Initialize recovery tracking files
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
    PACKET_ROUTE_HEADER_WRITTEN = False
    return LOG_FILE_NAME


def write_log(node_ref, message, sim_time=None):
    """Write structured log to file."""
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


def close_log_file():
    global LOG_FILE
    if LOG_FILE is not None:
        LOG_FILE.close()
        LOG_FILE = None


def log_packet_route(pck, current_node, next_hop_str, path_label):
    """Append routing trace rows to packet_routes.csv."""
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
    """Record end-to-end delay once a packet reaches its destination."""
    try:
        created = pck.get("created_at")
        if created is None:
            return
        delivered = getattr(receiver_node, "now", None)
        if delivered is None:
            return
        delay = delivered - created
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
                f"{delay:.6f}",
            ])
    except Exception:
        pass


def record_packet_path(pck, receiver_node):
    """Persist full path for traced data packets."""
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
    """Persist per-node join delays."""
    if wake_time is None or registered_time is None:
        return
    delay = registered_time - wake_time
    with open(REGISTRATION_LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([node_id, f"{wake_time:.6f}", f"{registered_time:.6f}", f"{delay:.6f}"])


def calculate_and_log_average_packet_delay():
    """Summarize packet delay statistics."""
    try:
        delays = []
        with open(PACKET_DELAY_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                delays.append(float(row["delay"]))
        if not delays:
            print("⚠️ No packet delays recorded.")
            return
        avg_delay = sum(delays) / len(delays)
        log_to_console_and_file(f"📦 Average packet delay: {avg_delay:.6f}s (samples={len(delays)})")
    except FileNotFoundError:
        log_to_console_and_file("⚠️ Packet delay log not found.")


def calculate_and_log_average_join_time():
    """Summarize node join time statistics."""
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
    """Log when a node becomes orphaned."""
    try:
        with open(ORPHAN_LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([node_id, f"{time:.6f}", reason, parent_id if parent_id else ""])
        ORPHANED_NODES.add(node_id)
    except Exception:
        pass


def log_role_change(node_id, old_role, new_role, time, reason=""):
    """Log when a node changes roles."""
    try:
        with open(ROLE_CHANGE_LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([node_id, _role_name(old_role), _role_name(new_role), f"{time:.6f}", reason])
    except Exception:
        pass


def log_recovery_event(node_id, failure_time, recovery_time, orphan_count, role_before, role_after):
    """Log when a failed node recovers."""
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
    """Write message to both console and log file."""
    print(message)
    if config.ENABLE_LOG_FILE and LOG_FILE is not None:
        try:
            LOG_FILE.write(message + "\n")
            LOG_FILE.flush()
        except Exception:
            pass


def calculate_and_log_recovery_statistics():
    """Generate recovery statistics report."""
    log_to_console_and_file("")
    log_to_console_and_file("="*70)


def log_packet_loss_statistics():
    """Summarize packet loss counters."""
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
    log_to_console_and_file("🔧 NETWORK RECOVERY STATISTICS")
    log_to_console_and_file("="*70)
    
    try:
        # Recovery events
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
        
        # Orphan events
        with open(ORPHAN_LOG_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            orphans = list(reader)
        
        if orphans:
            log_to_console_and_file(f"\n👥 Orphan Events: {len(orphans)} total")
            orphan_reasons = Counter([o['reason'] for o in orphans])
            for reason, count in orphan_reasons.most_common():
                log_to_console_and_file(f"   {reason}: {count} nodes")
        
        # Role changes
        with open(ROLE_CHANGE_LOG_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            role_changes = list(reader)
        
        if role_changes:
            log_to_console_and_file(f"\n🔄 Role Changes: {len(role_changes)} total")
            for rc in role_changes[:10]:  # Show first 10
                log_to_console_and_file(f"   Node {rc['node_id']}: {rc['old_role']} → {rc['new_role']} "
                      f"at {float(rc['time']):.1f}s ({rc['reason']})")
            if len(role_changes) > 10:
                log_to_console_and_file(f"   ... and {len(role_changes)-10} more role changes")
        
    except FileNotFoundError as e:
        log_to_console_and_file(f"\n⚠️  Recovery logs not found: {e}")
    except Exception as e:
        log_to_console_and_file(f"\n⚠️  Error generating recovery statistics: {e}")
    
    log_to_console_and_file("="*70)


###########################################################
# Energy Model Functions (CC2420 Radio)
###########################################################

def get_tx_current(tx_power_dbm):
    """Get TX current in Amperes for given TX power level (dBm).
    
    Args:
        tx_power_dbm (float): TX power in dBm (-25 to 0)
    
    Returns:
        float: TX current in Amperes
    """
    if tx_power_dbm not in config.TX_POWER_LEVELS:
        # Interpolate between known values
        sorted_powers = sorted(config.TX_POWER_LEVELS.keys())
        if tx_power_dbm < sorted_powers[0]:
            tx_power_dbm = sorted_powers[0]
        elif tx_power_dbm > sorted_powers[-1]:
            tx_power_dbm = sorted_powers[-1]
        else:
            # Find surrounding values and interpolate
            for i in range(len(sorted_powers) - 1):
                if sorted_powers[i] <= tx_power_dbm <= sorted_powers[i + 1]:
                    p1, p2 = sorted_powers[i], sorted_powers[i + 1]
                    i1, i2 = config.TX_POWER_LEVELS[p1], config.TX_POWER_LEVELS[p2]
                    # Linear interpolation
                    ratio = (tx_power_dbm - p1) / (p2 - p1)
                    current_ma = i1 + ratio * (i2 - i1)
                    return current_ma / 1000.0  # Convert mA to A
    
    current_ma = config.TX_POWER_LEVELS[tx_power_dbm]
    return current_ma / 1000.0  # Convert mA to Amperes


def calculate_tx_energy(packet_size_bytes, tx_power_dbm=0, include_pll_overhead=True):
    """Calculate energy required to transmit a packet (CC2420).
    
    Formula: E_tx = (V × I_TX × 8 × (N + 6)) / 250000 + E_overhead
    
    Args:
        packet_size_bytes (int): Packet payload size in bytes (PSDU)
        tx_power_dbm (float): TX power in dBm (default: 0 dBm)
        include_pll_overhead (bool): Include PLL turnaround overhead (default: True)
    
    Returns:
        float: Energy in Joules
    """
    if not config.ENABLE_ENERGY_MODEL:
        return 0.0
    
    # Get TX current for this power level
    i_tx = get_tx_current(tx_power_dbm)  # Amperes
    
    # Calculate transmission energy: E = (V × I × 8 × (N + 6)) / R
    # N = packet_size_bytes, 6 = PHY overhead, R = 250000 bps
    total_bytes = packet_size_bytes + config.CC2420_PHY_OVERHEAD
    total_bits = total_bytes * 8
    transmission_time = total_bits / config.CC2420_DATA_RATE  # seconds
    tx_energy = config.CC2420_VOLTAGE * i_tx * transmission_time  # Joules
    
    # Add PLL overhead if requested
    if include_pll_overhead:
        tx_energy += config.CC2420_PLL_OVERHEAD_ENERGY
    
    return tx_energy


def calculate_rx_energy(packet_size_bytes, include_pll_overhead=True):
    """Calculate energy required to receive a packet (CC2420).
    
    Args:
        packet_size_bytes (int): Packet payload size in bytes (PSDU)
        include_pll_overhead (bool): Include PLL turnaround overhead (default: True)
    
    Returns:
        float: Energy in Joules
    """
    if not config.ENABLE_ENERGY_MODEL:
        return 0.0
    
    # RX current is constant at 18.8 mA
    i_rx = config.CC2420_RX_CURRENT / 1000.0  # Convert mA to Amperes
    
    # Calculate reception energy: E = (V × I × 8 × (N + 6)) / R
    total_bytes = packet_size_bytes + config.CC2420_PHY_OVERHEAD
    total_bits = total_bytes * 8
    reception_time = total_bits / config.CC2420_DATA_RATE  # seconds
    rx_energy = config.CC2420_VOLTAGE * i_rx * reception_time  # Joules
    
    # Add PLL overhead if requested
    if include_pll_overhead:
        rx_energy += config.CC2420_PLL_OVERHEAD_ENERGY
    
    return rx_energy


def estimate_packet_size(packet):
    """Estimate packet size in bytes from packet dictionary.
    
    Args:
        packet (dict): Packet dictionary
    
    Returns:
        int: Estimated packet size in bytes
    """
    # Base packet structure overhead (estimate)
    base_overhead = 10  # bytes (MAC header, etc.)
    
    # Estimate payload size based on packet type
    packet_type = packet.get('type', 'UNKNOWN')
    
    if packet_type == 'HEART_BEAT':
        return 20 + base_overhead  # ~20 bytes payload
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
    elif packet_type == 'SENSOR':
        return 50 + base_overhead  # Data packets are larger
    elif packet_type == 'NEIGHBOR_SHARE':
        # Variable size based on number of neighbors
        neighbors_info = packet.get('neighbors_info', {})
        return 20 + len(neighbors_info) * 10 + base_overhead
    else:
        return 30 + base_overhead  # Default estimate


# Global dictionary to store cluster TX power assignments
# Format: {cluster_id (net_addr): tx_power_dbm}
CLUSTER_TX_POWER = {}


def get_cluster_tx_power(cluster_id):
    """Get TX power for a cluster.
    
    Args:
        cluster_id (int): Cluster ID (net_addr)
    
    Returns:
        float: TX power in dBm
    """
    if config.USE_GLOBAL_TX_POWER:
        return config.TX_POWER_DEFAULT
    
    # Check if cluster has assigned power
    if cluster_id in CLUSTER_TX_POWER:
        return CLUSTER_TX_POWER[cluster_id]
    
    # Default: use global default
    return config.TX_POWER_DEFAULT


def set_cluster_tx_power(cluster_id, tx_power_dbm):
    """Set TX power for a cluster.
    
    Args:
        cluster_id (int): Cluster ID (net_addr)
        tx_power_dbm (float): TX power in dBm (must be between TX_POWER_MIN and TX_POWER_MAX)
    """
    # Clamp to valid range
    tx_power_dbm = max(config.TX_POWER_MIN, min(config.TX_POWER_MAX, tx_power_dbm))
    CLUSTER_TX_POWER[cluster_id] = tx_power_dbm
    
    if config.ENABLE_ENERGY_DEBUG:
        log_to_console_and_file(f"[ENERGY] Cluster {cluster_id} TX power set to {tx_power_dbm} dBm")


def optimize_clusters():
    """Cluster optimization protocol to minimize clusters or energy consumption.
    
    This function can be called periodically to optimize the network.
    """
    if not config.ENABLE_CLUSTER_OPTIMIZATION:
        return
    
    # Get all active cluster heads
    active_chs = [node for node in ALL_NODES 
                  if node.role == Roles.CLUSTER_HEAD and not node.is_shutdown and node.ch_addr is not None]
    
    if len(active_chs) <= 1:
        return  # No optimization needed with 0 or 1 cluster
    
    if config.CLUSTER_OPTIMIZATION_MODE == 'CLUSTERS':
        # Minimize number of clusters by merging nearby clusters
        # Simple strategy: If two clusters are very close, merge them
        # This is a placeholder - can be enhanced with more sophisticated algorithms
        if config.ENABLE_ENERGY_DEBUG:
            log_to_console_and_file(f"[CLUSTER_OPT] Running cluster minimization (current: {len(active_chs)} clusters)")
        # TODO: Implement cluster merging logic
        
    elif config.CLUSTER_OPTIMIZATION_MODE == 'ENERGY':
        # Minimize energy consumption by optimizing TX power per cluster
        if config.ENABLE_ENERGY_DEBUG:
            log_to_console_and_file(f"[CLUSTER_OPT] Running energy optimization (current: {len(active_chs)} clusters)")
        
        for ch in active_chs:
            cluster_id = ch.ch_addr.net_addr
            member_count = len(ch.members_table)
            
            # Calculate optimal TX power based on cluster characteristics
            # Strategy: Use minimum power that maintains connectivity
            # For now, use a simple heuristic: smaller clusters can use lower power
            if member_count <= 3:
                # Small cluster - can use lower power
                optimal_power = max(config.TX_POWER_MIN, config.TX_POWER_DEFAULT - 10)
            elif member_count <= 10:
                # Medium cluster - use medium power
                optimal_power = config.TX_POWER_DEFAULT - 5
            else:
                # Large cluster - use default/max power for reliability
                optimal_power = config.TX_POWER_DEFAULT
            
            # Update cluster TX power if different
            current_power = get_cluster_tx_power(cluster_id)
            if abs(current_power - optimal_power) > 1.0:  # Only update if significant difference
                set_cluster_tx_power(cluster_id, optimal_power)
                
                # Update all nodes in this cluster
                for node in ALL_NODES:
                    if node.ch_addr is not None and node.ch_addr.net_addr == cluster_id:
                        node.update_cluster_tx_power()
                
                if config.ENABLE_ENERGY_DEBUG:
                    log_to_console_and_file(f"[CLUSTER_OPT] Cluster {cluster_id}: TX power optimized from {current_power} to {optimal_power} dBm (members={member_count})")


Roles = Enum('Roles', 'UNDISCOVERED UNREGISTERED ROOT REGISTERED CLUSTER_HEAD ROUTER')
"""Enumeration of roles"""

###########################################################
class SensorNode(wsn.Node):
    """SensorNode class is inherited from Node class in wsnlab.py.
    It will run data collection tree construction algorithms.

    Attributes:
        role (Roles): role of node
        is_root_eligible (bool): keeps eligibility to be root
        c_probe (int): probe message counter
        th_probe (int): probe message threshold
        neighbors_table (Dict): keeps the neighbor information with received heart beat messages
    """

    ###################
    def init(self):
        """Initialization of node. Setting all attributes of node.
        At the beginning node needs to be sleeping and its role should be UNDISCOVERED.

        Args:

        Returns:

        """
        self.scene.nodecolor(self.id, 1, 1, 1) # sets self color to white
        self.sleep()
        self.addr = None
        self.ch_addr = None
        self.parent_gui = None
        self.root_addr = None
        self.wake_up_time = None
        self.registered_time = None
        self.tx_range_circle_id = None  # Initialize TX range circle ID for visualization
        self.set_role(Roles.UNDISCOVERED)
        self.is_root_eligible = True if self.id == ROOT_ID else False
        self.c_probe = 0  # c means counter and probe is the name of counter
        self.th_probe = 10  # th means threshold and probe is the name of threshold
        self.hop_count = 99999
        self.neighbors_table = {}  # keeps neighbor information with received HB messages
        self.candidate_parents_table = []
        self.child_networks_table = {}
        self.members_table = []  # List of member addresses
        self.received_JR_guis = []  # keeps received Join Request global unique ids
        
        # Address pool for cluster size control (simple and clean)
        self.node_addr_pool = {}  # {node_addr: gui or None} - pool of available addresses for children
        self.cluster_addr_pool = {}
        
        # Energy Model (CC2420)
        self.energy_remaining = config.BATTERY_ENERGY_TOTAL  # Joules - initial battery energy
        self.energy_initial = config.BATTERY_ENERGY_TOTAL  # Joules - track initial energy
        self.energy_tx_total = 0.0  # Total TX energy consumed (Joules)
        self.energy_rx_total = 0.0  # Total RX energy consumed (Joules)
        self.energy_baseline_total = 0.0  # Total baseline energy consumed (Joules)
        self.is_shutdown = False  # Flag to indicate if node is shut down due to low energy
        self.shutdown_time = None  # Time when node was shut down
        
        # TX Power Configuration
        self.tx_power_dbm = config.TX_POWER_DEFAULT  # Current TX power in dBm
        self.cluster_tx_power_dbm = None  # TX power assigned to this node's cluster
        
        # Debug: Log initial energy assignment
        if config.ENABLE_ENERGY_MODEL and config.ENABLE_ENERGY_DEBUG:
            msg = f"[ENERGY] Node {self.id}: Initialized with {self.energy_remaining:.6f}J ({config.BATTERY_ENERGY_TOTAL:.6f}J total, TX power={self.tx_power_dbm}dBm)"
            self.log(msg)
            write_log(self, msg)
        
        # Proactive CH creation state
        self.failed_join_attempts = 0  # Count of failed join attempts for UNREGISTERED nodes
        self.registered_since = None  # Time when node became REGISTERED (for proactive CH creation)  # {cluster_id: source or None} - pool of cluster IDs (ROOT only)
        
        # Multi-hop neighbor discovery
        self.multihop_neighbor_table = {}  # {neighbor_gui: {'hop_dist': int, 'next_hop': gui, 'distance': float}}
        
        # Node failure and recovery tracking
        self.is_failed = False
        self.failure_time = None
        self.role_before_failure = None
        self.children_before_failure = []
        
        # Router/CH transfer state (for overlap reduction)
        self.ch_transfer_enabled = getattr(config, 'ENABLE_CH_TRANSFER', True)
        self.ch_transfer_in_progress = False
        self.ch_transfer_candidate = None  # GUI of node being transferred to
        
        # Proactive CH creation state
        self.failed_join_attempts = 0  # Count of failed join attempts for UNREGISTERED nodes
        self.registered_since = None  # Time when node became REGISTERED (for proactive CH creation)
        
        # Rate limiting for JOIN_REPLY resends (prevent spam loops)
        self.join_reply_last_sent = {}  # {child_gui: last_sent_time}
        self.join_reply_cooldown = 5.0  # Minimum seconds between resends
        
        # Rate limiting for JOIN_REQUEST sends (prevent spam)
        self.last_join_request_sent_time = None  # timestamp of last JOIN_REQUEST
        self.join_request_cooldown = 20  # seconds between JOIN_REQUEST sends
        
        # Rate limiting for TRIGGER_CH_CREATION sends (prevent spam)
        self.last_trigger_ch_creation_time = None  # Timestamp of last TRIGGER_CH_CREATION sent
        self.trigger_ch_creation_cooldown = 60.0  # Cooldown period for TRIGGER_CH_CREATION (seconds) - prevent spam
        
        # Track heartbeat timer for ROUTER nodes
        self.heartbeat_timer_active = False

    ###################
    def run(self):
        """Setting the arrival timer to wake up after firing.

        Args:

        Returns:

        """
        self.set_timer('TIMER_ARRIVAL', self.arrival)

    ###################
    def debug_log(self, enabled, message):
        """Log to console and file when enabled."""
        if enabled:
            self.log(message)
            write_log(self, message)

    ###################

    def set_role(self, new_role, *, recolor=True, reason=""):
        """Central place to switch roles, keep tallies, and (optionally) recolor."""
        old_role = getattr(self, "role", None)
        if old_role is not None:
            ROLE_COUNTS[old_role] -= 1
            if ROLE_COUNTS[old_role] <= 0:
                ROLE_COUNTS.pop(old_role, None)
        ROLE_COUNTS[new_role] += 1
        self.role = new_role
        
        # Log role changes (except for initial UNDISCOVERED)
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
            elif new_role == Roles.ROOT:
                self.scene.nodecolor(self.id, 0, 0, 0)
                self.draw_tx_range()  # ROOT should also draw its TX range
                self.set_timer('TIMER_EXPORT_CH_CSV', config.EXPORT_CH_CSV_INTERVAL)
                self.set_timer('TIMER_EXPORT_NEIGHBOR_CSV', config.EXPORT_NEIGHBOR_CSV_INTERVAL)
            elif new_role == Roles.ROUTER:
                # Magenta/pink color to distinguish from CH (blue)
                self.scene.nodecolor(self.id, 1, 0, 0.75)
                # Remove TX range circle when becoming router
                if hasattr(self, 'tx_range_circle_id') and self.tx_range_circle_id is not None:
                    try:
                        self.scene.delshape(self.tx_range_circle_id)
                        self.tx_range_circle_id = None
                    except:
                        pass

    ###################
    # Router and CH Transfer Methods (for overlap reduction)
    ###################
    
    def become_router(self, reason="CH role transferred"):
        """Convert this node from CLUSTER_HEAD to ROUTER.
        Router acts as a bridge between cluster heads, forwarding packets.
        """
        if self.role != Roles.CLUSTER_HEAD or self.id == ROOT_ID:
            return  # Only CHs can become routers, and ROOT never becomes router
        
        prev_ch_addr = self.ch_addr
        self.ch_addr = None  # Router doesn't have its own cluster
        self.set_role(Roles.ROUTER, reason=reason)
        
        # CRITICAL: ROUTER nodes must send periodic HEART_BEAT so UNREGISTERED nodes can discover them
        # This allows UNREGISTERED nodes to join the network through routers
        if not hasattr(self, 'heartbeat_timer_active') or not self.heartbeat_timer_active:
            self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
            self.heartbeat_timer_active = True
        
        if config.ENABLE_CLUSTER_DEBUG:
            self.log(f"[ROUTER] Node {self.id} became ROUTER (prev_ch={format_addr(prev_ch_addr)})")
            write_log(self, f"[ROUTER] Node {self.id} activated as router")
    
    def find_farthest_member(self):
        """
        Find the farthest registered member from this CLUSTER_HEAD.
        This member will be nominated to become the new CH to reduce overlap.
        Returns (member_gui, member_addr, distance) or (None, None, -1) if no candidate.
        """
        if self.role != Roles.CLUSTER_HEAD or len(self.members_table) == 0:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[CH_TRANSFER] Node {self.id}: Cannot find candidate - role={self.role}, members={len(self.members_table)}")
            return None, None, -1
        
        # Convert member addresses to hashable keys for set operations
        member_addr_keys = {addr_key(addr) for addr in self.members_table if addr is not None}
        best_gui, best_addr, best_dist = None, None, -1.0
        candidates_checked = 0
        members_without_neighbor_info = []
        
        # First, try to find members in neighbors_table with distance info
        for neighbor_gui, neighbor_info in self.neighbors_table.items():
            neighbor_addr = neighbor_info.get('addr')
            
            # Must be a registered member - use addr_key for comparison
            if addr_key(neighbor_addr) not in member_addr_keys:
                continue
            
            candidates_checked += 1
            
            # Never transfer to ROOT
            if neighbor_gui == ROOT_ID:
                continue
            
            # Must have distance information
            distance = neighbor_info.get('distance')
            if distance is None:
                if config.ENABLE_CLUSTER_DEBUG:
                    self.log(f"[CH_TRANSFER] Node {self.id}: Neighbor {neighbor_gui} has no distance info")
                continue
            
            # Choose the farthest member to push CH outward
            if distance > best_dist:
                best_gui = neighbor_gui
                best_addr = neighbor_addr
                best_dist = distance
        
        # If no candidate found in neighbors_table, try to find member by address
        # This handles cases where member joined but hasn't sent heartbeat yet
        if best_gui is None and len(self.members_table) > 0:
            # Find any member address and try to locate the node
            for member_addr in self.members_table:
                member_node = self._find_node_by_addr(member_addr)
                if member_node and member_node.id != ROOT_ID and member_node.id != self.id:
                    # Calculate distance if we have positions
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
        """
        Trigger nearby REGISTERED nodes to become cluster heads.
        Sends TRIGGER_CH_CREATION message to REGISTERED neighbors via broadcast.
        Rate-limited to prevent spam.
        """
        if self.role != Roles.UNREGISTERED:
            return
        
        # Rate limiting: Don't send TRIGGER_CH_CREATION too frequently
        if self.last_trigger_ch_creation_time is not None:
            time_since_last = self.now - self.last_trigger_ch_creation_time
            if time_since_last < self.trigger_ch_creation_cooldown:
                if config.ENABLE_CLUSTER_DEBUG:
                    self.log(f"[CH_CREATION] Node {self.id}: Rate-limiting TRIGGER_CH_CREATION (last sent {time_since_last:.1f}s ago, cooldown={self.trigger_ch_creation_cooldown}s)")
                return
        
        # Find REGISTERED neighbors - use broadcast since UNREGISTERED nodes don't have addresses
        found_registered = False
        for neighbor_gui, neighbor_info in self.neighbors_table.items():
            neighbor_role = neighbor_info.get('role')
            if neighbor_role == Roles.REGISTERED:
                found_registered = True
                # Use broadcast to reach REGISTERED neighbors (they'll filter by type)
                trigger_pck = {
                    'dest': wsn.BROADCAST_ADDR,  # Broadcast so REGISTERED nodes can receive it
                    'type': 'TRIGGER_CH_CREATION',
                    'source': self.addr if self.addr else wsn.BROADCAST_ADDR,
                    'gui': self.id,
                    'target_gui': neighbor_gui  # Specify which neighbor we want to trigger
                }
                # Use direct send instead of route_and_forward_package since we're broadcasting
                self.send(trigger_pck)
                self.last_trigger_ch_creation_time = self.now  # Update timestamp
                self.log(f"[CH_CREATION] Node {self.id}: Sent TRIGGER_CH_CREATION broadcast (target REGISTERED neighbor {neighbor_gui})")
                break  # Only trigger one neighbor to avoid multiple CHs
        
        if not found_registered:
            # No REGISTERED neighbors - send general broadcast hoping any REGISTERED node will respond
            trigger_pck = {
                'dest': wsn.BROADCAST_ADDR,
                'type': 'TRIGGER_CH_CREATION',
                'source': self.addr if self.addr else wsn.BROADCAST_ADDR,
                'gui': self.id,
                'target_gui': None  # No specific target - any REGISTERED node can respond
            }
            self.send(trigger_pck)
            self.last_trigger_ch_creation_time = self.now  # Update timestamp
            self.log(f"[CH_CREATION] Node {self.id}: Sent TRIGGER_CH_CREATION broadcast (no REGISTERED neighbors in table, hoping any REGISTERED node responds)")
    
    def initiate_ch_transfer(self):
        """
        Initiate CH role transfer to reduce cluster overlap.
        Finds the farthest member and sends them a CH_TRANSFER message.
        """
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
        
        # Need at least one member to transfer to
        min_members = getattr(config, 'MIN_MEMBERS_FOR_TRANSFER', 1)
        if len(self.members_table) < min_members:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[CH_TRANSFER] Node {self.id}: Not enough members ({len(self.members_table)} < {min_members})")
            return
        
        # Find farthest member
        candidate_gui, candidate_addr, candidate_dist = self.find_farthest_member()
        
        if candidate_gui is None:
            if config.ENABLE_CLUSTER_DEBUG:
                self.log(f"[CH_TRANSFER] Node {self.id}: No candidate found (members={len(self.members_table)})")
            return  # No suitable candidate found
        
        # Mark transfer as in progress
        self.ch_transfer_in_progress = True
        self.ch_transfer_candidate = candidate_gui
        
        # Send CH_TRANSFER message to candidate
        transfer_pck = {
            'dest': candidate_addr,
            'type': 'CH_TRANSFER',
            'source': self.addr,
            'gui': self.id,
            'new_ch_addr': self.ch_addr,  # The CH address to adopt
            'prev_ch_addr': self.ch_addr
        }
        
        # Use routing to ensure packet reaches destination
        self.route_and_forward_package(transfer_pck)
        
        self.log(f"[CH_TRANSFER] Node {self.id} transferring CH role to node {candidate_gui} (dist={candidate_dist:.1f}m, addr={format_addr(candidate_addr)})")
        write_log(self, f"[CH_TRANSFER] Initiating transfer from CH {self.id} to member {candidate_gui} (dist={candidate_dist:.1f}m)")

    ###################
    # Node Failure and Recovery Methods
    ###################
    
    def fail_node(self):
        """Simulate node failure - node stops all operations."""
        if self.is_failed or self.role == Roles.ROOT:
            return  # Cannot fail ROOT or already failed node
        
        # Only fail nodes that have joined the network (REGISTERED or CLUSTER_HEAD)
        if self.role not in [Roles.REGISTERED, Roles.CLUSTER_HEAD]:
            if config.ENABLE_RECOVERY_DEBUG:
                self.log(f"[RECOVERY] Node {self.id} failure skipped - not yet registered (role: {_role_name(self.role)})")
            return
        
        self.is_failed = True
        self.failure_time = self.sim.now
        self.role_before_failure = self.role
        self.children_before_failure = list(self.members_table)
        
        # Track as failed
        FAILED_NODES.add(self.id)
        
        # Mark children as orphans
        orphan_count = 0
        for child_addr in self.members_table:
            child_node = self._find_node_by_addr(child_addr)
            if child_node:
                child_node.become_orphan(f"Parent node {self.id} failed")
                orphan_count += 1
        
        # Stop all operations
        self.kill_all_timers()
        
        # Change visual state
        self.scene.nodecolor(self.id, 0.5, 0.5, 0.5)  # Gray color for failed
        
        # Log the failure
        if config.ENABLE_RECOVERY_DEBUG:
            self.log(f"[RECOVERY] Node {self.id} FAILED at {self.sim.now:.2f}s | "
                    f"Role: {_role_name(self.role_before_failure)} | "
                    f"Orphaned children: {orphan_count}")
        
        log_role_change(self.id, self.role_before_failure, Roles.UNDISCOVERED, 
                       self.sim.now, f"Node failed (orphaned {orphan_count} children)")
    
    def recover_node(self):
        """Simulate node recovery - node restarts and rejoins network."""
        if not self.is_failed:
            return
        
        recovery_time = self.sim.now
        downtime = recovery_time - self.failure_time
        orphan_count = len([n for n in ALL_NODES if n.id in ORPHANED_NODES])
        
        # Clear failure state
        self.is_failed = False
        FAILED_NODES.discard(self.id)
        
        # Log recovery event
        log_recovery_event(self.id, self.failure_time, recovery_time, 
                          orphan_count, self.role_before_failure, Roles.UNDISCOVERED)
        
        if config.ENABLE_RECOVERY_DEBUG:
            self.log(f"[RECOVERY] Node {self.id} RECOVERED at {recovery_time:.2f}s | "
                    f"Downtime: {downtime:.2f}s | "
                    f"Network orphans: {orphan_count}")
        
        # Restart as undiscovered node
        self.scene.nodecolor(self.id, 1, 1, 1)  # White color
        self.addr = None
        self.ch_addr = None
        self.parent_gui = None
        self.members_table = []
        self.received_JR_guis = []
        self.neighbors_table = {}
        self.multihop_neighbor_table = {}
        self.hop_count = 99999
        self.set_role(Roles.UNDISCOVERED, reason=f"Node recovered after {downtime:.2f}s downtime")
        
        # Start network discovery (use same timing as normal PROBE timer)
        self.set_timer('TIMER_PROBE', 1)
    
    def become_orphan(self, reason=""):
        """Mark node as orphaned and initiate recovery."""
        if self.is_failed or self.role == Roles.ROOT:
            return
        
        # Log orphan event
        log_orphan_event(self.id, self.sim.now, reason, self.parent_gui)
        
        if config.ENABLE_RECOVERY_DEBUG:
            self.log(f"[RECOVERY] Node {self.id} became ORPHAN | Reason: {reason}")
        
        # Become unregistered and search for new parent
        self.become_unregistered()
        
        # Mark own children as orphans too
        for child_addr in list(self.members_table):
            child_node = self._find_node_by_addr(child_addr)
            if child_node and not child_node.is_failed:
                child_node.become_orphan(f"Parent node {self.id} became orphan")
    
    def _find_node_by_addr(self, addr):
        """Find node by network address."""
        if addr is None:
            return None
        for node in ALL_NODES:
            if node.addr is not None and addr_equals(node.addr, addr):
                return node
        return None
    
    def _find_node_by_gui(self, gui):
        """Find node by GUI ID."""
        if gui is None:
            return None
        for node in ALL_NODES:
            if node.id == gui:
                return node
        return None

    
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
        self.candidate_parents_table = []
        self.child_networks_table = {}
        self.members_table = []
        self.received_JR_guis = []  # keeps received Join Request global unique ids
        self.failed_join_attempts = 0  # Reset failed attempts when becoming UNREGISTERED
        self.last_trigger_ch_creation_time = None  # Track when we last sent TRIGGER_CH_CREATION
        self.send_probe()
        self.set_timer('TIMER_JOIN_REQUEST', 20)

    ###################
    def update_neighbor(self, pck):
        """Update 1-hop neighbor info from heartbeat and add to multihop table"""
        neighbor_entry = pck.copy()
        neighbor_entry['arrival_time'] = self.now
        # compute Euclidean distance between self and neighbor
        if neighbor_entry['gui'] in NODE_POS and self.id in NODE_POS:
            x1, y1 = NODE_POS[self.id]
            x2, y2 = NODE_POS[neighbor_entry['gui']]
            neighbor_entry['distance'] = math.hypot(x1 - x2, y1 - y2)
        neighbor_entry['mesh_hop_distance'] = 1
        
        neighbor_gui = neighbor_entry['gui']
        old_entry = self.neighbors_table.get(neighbor_gui)
        self.neighbors_table[neighbor_gui] = neighbor_entry

        # Only add to candidate_parents_table if:
        # 1. Not in child_networks_table (not our child)
        # 2. Has a valid role that can be a parent (REGISTERED, CLUSTER_HEAD, ROUTER, or ROOT)
        # 3. Not already in candidate_parents_table
        # 4. Has a valid address (can accept JOIN_REQUESTs)
        neighbor_role = neighbor_entry.get('role')
        # For address, prefer 'source' (CH address or node address) as that's what we'll send JOIN_REQUEST to
        # For ROUTER nodes, they might not have ch_addr, so use 'addr' (their node address)
        # Fall back to 'ch_addr' if 'source' and 'addr' are not available
        neighbor_addr = neighbor_entry.get('source') or neighbor_entry.get('addr') or neighbor_entry.get('ch_addr')
        
        # Check if role is valid - handle both Enum and string comparisons
        # CRITICAL: Only CLUSTER_HEAD, ROUTER, and ROOT can be parents
        # REGISTERED nodes cannot accept children until they become CLUSTER_HEAD
        valid_roles = (Roles.CLUSTER_HEAD, Roles.ROUTER, Roles.ROOT)
        has_valid_role = (neighbor_role in valid_roles) if neighbor_role is not None else False
        has_valid_addr = (neighbor_addr is not None)
        can_be_parent = has_valid_role and has_valid_addr
        
        if neighbor_gui not in self.child_networks_table.keys():
            # Check if this neighbor was previously rejected but now has valid role
            was_in_candidates = neighbor_gui in self.candidate_parents_table
            
            if can_be_parent:
                # Add to candidate_parents_table if not already there
                if neighbor_gui not in self.candidate_parents_table:
                    self.candidate_parents_table.append(neighbor_gui)
                    if self.role in (Roles.UNDISCOVERED, Roles.UNREGISTERED):
                        write_log(self, f"[JOIN] Node {self.id}: Added candidate parent {neighbor_gui} (role={neighbor_role}, addr={format_addr(neighbor_addr)})")
                elif old_entry and old_entry.get('role') != neighbor_role:
                    # Role changed - log it for debugging
                    if self.role in (Roles.UNDISCOVERED, Roles.UNREGISTERED):
                        write_log(self, f"[JOIN] Node {self.id}: Candidate parent {neighbor_gui} role updated {old_entry.get('role')} -> {neighbor_role}")
            elif not can_be_parent and config.ENABLE_CLUSTER_DEBUG and self.role in (Roles.UNDISCOVERED, Roles.UNREGISTERED):
                # Debug why neighbor can't be parent
                reason = []
                if not has_valid_role:
                    reason.append(f"invalid_role={neighbor_role} (type={type(neighbor_role).__name__})")
                if not has_valid_addr:
                    reason.append("no_addr")
                # Log every time we reject a neighbor if we have no candidates (helps debug)
                # But limit logging to avoid spam - only log first few rejections
                if reason and len(self.candidate_parents_table) == 0 and len(self.neighbors_table) <= 5:
                    write_log(self, f"[JOIN] Node {self.id}: Neighbor {neighbor_gui} cannot be parent ({', '.join(reason)}, entry_keys={list(neighbor_entry.keys())})")
        
        # Add to multihop neighbor table as 1-hop neighbor
        if config.ENABLE_MULTIHOP_DISCOVERY:
            neighbor_gui = neighbor_entry['gui']
            euclidean_dist = neighbor_entry.get('distance', 0)
            
            # Update or add as 1-hop neighbor
            self.multihop_neighbor_table[neighbor_gui] = {
                'hop_dist': 1,
                'next_hop': neighbor_gui,  # Direct neighbor
                'distance': euclidean_dist,
                'addr': neighbor_entry.get('addr')
            }
            
            if config.ENABLE_NEIGHBOR_DEBUG:
                msg = f"[NEIGHBOR_1HOP] Discovered neighbor {neighbor_gui} at distance {euclidean_dist:.2f}m"
                self.log(msg)
                write_log(self, msg)

    ###################
    def process_neighbor_share(self, pck):
        """Process neighbor info shared by neighbors (Distance Vector style)"""
        if not config.ENABLE_MULTIHOP_DISCOVERY:
                        return

        sender_gui = pck['gui']
        neighbors_info = pck.get('neighbors_info', {})
        
        # Check if sender is a 1-hop neighbor
        if sender_gui not in self.neighbors_table:
            return  # Ignore if not a direct neighbor
        
        learned_count = 0
        
        for neighbor_gui, info in neighbors_info.items():
            # Don't learn about ourselves
            if neighbor_gui == self.id:
                continue
            
            new_hop_dist = info['hop_dist'] + 1  # Add 1 hop through sender
            
            # Only add if within MAX_HOP_DISTANCE
            if new_hop_dist > config.MAX_HOP_DISTANCE:
                continue
            
            # Update if new neighbor OR found shorter path
            if neighbor_gui not in self.multihop_neighbor_table or \
               new_hop_dist < self.multihop_neighbor_table[neighbor_gui]['hop_dist']:
                
                self.multihop_neighbor_table[neighbor_gui] = {
                    'hop_dist': new_hop_dist,
                    'next_hop': sender_gui,  # Route through sender
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

    ###################
    def select_and_join(self):
        # Don't send JOIN_REQUEST if already registered
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
            # Only consider neighbors that can actually be parents (have valid roles)
            # CRITICAL: Only CLUSTER_HEAD, ROUTER, and ROOT can accept children
            neighbor_role = neighbor_info.get('role')
            valid_roles = (Roles.CLUSTER_HEAD, Roles.ROUTER, Roles.ROOT)
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
        # Try 'source' first (CH address or node address), then 'ch_addr', then 'addr'
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
        # Don't set timer here - let TIMER_JOIN_REQUEST handler manage the timer
        # This prevents duplicate timer scheduling


    ###################
    def send_probe(self):
        """Sending probe message to be discovered and registered.

        Args:

        Returns:

        """
        self.send({'dest': wsn.BROADCAST_ADDR, 'type': 'PROBE'})

    ###################
    def send_heart_beat(self):
        """Sending heart beat message

        Args:

        Returns:

        """
        # UNREGISTERED and UNDISCOVERED nodes should NOT send heartbeats
        # Only ROOT, CLUSTER_HEAD, REGISTERED, and ROUTER nodes should send heartbeats
        if self.role in (Roles.UNREGISTERED, Roles.UNDISCOVERED):
            return  # Do not send heartbeat if node is not registered
        
        self.send({'dest': wsn.BROADCAST_ADDR,
                   'type': 'HEART_BEAT',
                   'source': self.ch_addr if self.ch_addr is not None else self.addr,
                   'gui': self.id,
                   'role': self.role,
                   'addr': self.addr,
                   'ch_addr': self.ch_addr,
                   'hop_count': self.hop_count})

    ###################
    def share_neighbor_info(self):
        """Share multihop neighbor table with 1-hop neighbors (Distance Vector style)"""
        if not config.ENABLE_MULTIHOP_DISCOVERY:
            return
        
        # Only share if we have neighbors to share
        if len(self.multihop_neighbor_table) == 0:
            return
        
        # Prepare neighbor info to share (only up to MAX_HOP_DISTANCE - 1)
        neighbors_to_share = {}
        for neighbor_gui, info in self.multihop_neighbor_table.items():
            if info['hop_dist'] < config.MAX_HOP_DISTANCE:
                neighbors_to_share[neighbor_gui] = {
                    'hop_dist': info['hop_dist'],
                    'distance': info['distance'],
                    'addr': info.get('addr')
                }
        
        if len(neighbors_to_share) == 0:
            return
        
        # Send to all 1-hop neighbors
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

    ###################
    def send_join_request(self, dest):
        """Sending join request message to given destination address to join destination network

        Args:
            dest (Addr): Address of destination node
        Returns:

        """
        # Rate limiting is now handled in TIMER_JOIN_REQUEST handler
        # Just send the JOIN_REQUEST (rate limit check already done)
        # Update timestamp BEFORE sending to ensure rate limit works correctly
        old_time = self.last_join_request_sent_time
        self.last_join_request_sent_time = self.now
        self.send({'dest': dest, 'type': 'JOIN_REQUEST', 'gui': self.id})
        if config.ENABLE_CLUSTER_DEBUG:
            write_log(self, f"[JOIN] Node {self.id}: Sent JOIN_REQUEST to {format_addr(dest)}")

    ###################
    def send_join_reply(self, gui, addr):
        """Sending join reply message to register the node requested to join.
        The message includes a gui to determine which node will take this reply, an addr to be assigned to the node
        and a root_addr.

        Args:
            gui (int): Global unique ID
            addr (Addr): Address that will be assigned to new registered node
        Returns:

        """
        self.send({'dest': wsn.BROADCAST_ADDR, 'type': 'JOIN_REPLY', 'source': self.ch_addr,
                   'gui': self.id, 'dest_gui': gui, 'addr': addr, 'root_addr': self.root_addr,
                   'hop_count': self.hop_count+1})

    ###################
    def send_join_ack(self, dest):
        """Sending join acknowledgement message to given destination address.

        Args:
            dest (Addr): Address of destination node
        Returns:

        """
        self.send({'dest': dest, 'type': 'JOIN_ACK', 'source': self.addr,
                   'gui': self.id})

    ###################
    def send(self, pck):
        """Ensure every packet carries a creation timestamp and prevent routing loops."""
        # Check if node is shut down due to low energy
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
            return  # simulate packet lost on the channel
        
        # Calculate and deduct TX energy (before sending, even if packet is lost)
        if config.ENABLE_ENERGY_MODEL:
            packet_size = estimate_packet_size(pck)
            # Get TX power for this node (cluster-based or global)
            if self.ch_addr is not None:
                cluster_id = self.ch_addr.net_addr
                tx_power = get_cluster_tx_power(cluster_id)
            else:
                tx_power = self.tx_power_dbm
            
            tx_energy = calculate_tx_energy(packet_size, tx_power, include_pll_overhead=True)
            
            # Deduct energy
            if self.energy_remaining >= tx_energy:
                self.energy_remaining -= tx_energy
                self.energy_tx_total += tx_energy
                
                if config.ENABLE_ENERGY_DEBUG:
                    energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
                    msg = f"[ENERGY] Node {self.id}: TX {p_type} ({packet_size}B, {tx_power}dBm) - {tx_energy*1e6:.3f}µJ, remaining={self.energy_remaining:.6f}J ({energy_percent:.2f}%)"
                    self.log(msg)
                    write_log(self, msg)
            else:
                # Not enough energy - shut down node
                if config.ENABLE_ENERGY_DEBUG:
                    msg = f"[ENERGY] Node {self.id}: Insufficient energy for TX {p_type} - need {tx_energy*1e6:.3f}µJ, have {self.energy_remaining*1e6:.3f}µJ"
                    self.log(msg)
                    write_log(self, msg)
                self.energy_remaining = 0.0
                self.shutdown_node("Insufficient energy for transmission")
                return

        # CRITICAL: Prevent routing loops while trusting routing decisions
        # If routing has determined a specific next_hop, trust that decision
        route_trace = pck.get('route_trace', [])
        next_hop = pck.get('next_hop')
        dest = pck.get('dest')
        
        # CRITICAL: If packet is for ourselves (dest == self.addr or next_hop == self.addr), don't send
        # The packet is already being processed in on_receive(), sending it again would create a loop
        if self.addr is not None:
            if addr_equals(dest, self.addr) or addr_equals(next_hop, self.addr):
                if config.ENABLE_ROUTING_DEBUG:
                    self.log(f"[ROUTING] Node {self.id}: Packet for self (dest={format_addr(dest)}, next_hop={format_addr(next_hop)}), not sending to prevent loop")
                return
        
        # Check if dest is broadcast
        is_broadcast = False
        if dest is not None and hasattr(dest, 'is_equal'):
            is_broadcast = dest.is_equal(wsn.BROADCAST_ADDR)
        
        # If we have a specific next_hop (not broadcast), trust the routing decision
        # Only filter by route_trace for broadcasts or when next_hop is not specific
        has_specific_next_hop = (next_hop is not None and 
                                not is_broadcast and 
                                (not hasattr(next_hop, 'is_equal') or not next_hop.is_equal(wsn.BROADCAST_ADDR)))
        
        if has_specific_next_hop and route_trace:
            # Trust routing decision: send to nodes matching next_hop even if in route_trace
            # This allows packets to reach their intended destination even if it was in the path
            sent = False
            for (dist, node) in self.neighbor_distance_list:
                if dist <= self.tx_range:
                    # CRITICAL: Don't send to ourselves (prevents infinite loop)
                    if node.id == self.id:
                        continue
                    if node.can_receive(pck):
                        # Check if this node matches the next_hop address
                        if node.addr is not None and addr_equals(node.addr, next_hop):
                            # Found the intended recipient - send even if in route_trace
                            prop_time = dist / 1000000 - 0.00001 if dist / 1000000 - 0.00001 > 0 else 0.00001
                            self.delayed_exec(prop_time, node.on_receive_check, pck)
                            sent = True
                            if config.ENABLE_ROUTING_DEBUG and node.id in route_trace:
                                self.log(f"[ROUTING] Node {self.id}: Sending to intended next_hop {node.id} (in route_trace but routing decision trusted)")
                            break  # Only send to first matching node
                else:
                    break
            if not sent:
                if config.ENABLE_ROUTING_DEBUG:
                    self.log(f"[ROUTING] Node {self.id}: Intended next_hop {format_addr(next_hop)} not found in neighbors")
            return
        
        # For broadcasts or packets without specific next_hop, filter by route_trace
        if route_trace and not is_broadcast:
            filtered_neighbors = []
            for (dist, node) in self.neighbor_distance_list:
                if dist <= self.tx_range:
                    # Skip nodes already in route_trace (prevent loops)
                    if node.id in route_trace:
                        if config.ENABLE_ROUTING_DEBUG:
                            self.log(f"[ROUTING] Node {self.id}: Skipping neighbor {node.id} - already in route_trace {route_trace}")
                        continue
                    # Check if this node can receive the packet
                    if node.can_receive(pck):
                        filtered_neighbors.append((dist, node))
                else:
                    break
            
            # Send only to filtered neighbors
            if filtered_neighbors:
                for (dist, node) in filtered_neighbors:
                    prop_time = dist / 1000000 - 0.00001 if dist / 1000000 - 0.00001 > 0 else 0.00001
                    self.delayed_exec(prop_time, node.on_receive_check, pck)
            else:
                if config.ENABLE_ROUTING_DEBUG:
                    self.log(f"[ROUTING] Node {self.id}: No valid neighbors (all in route_trace {route_trace})")
            return

        # For broadcast packets or packets without route_trace, use normal send
        super().send(pck)

    ###################
    def shutdown_node(self, reason="Low energy"):
        """Shutdown node when energy drops below minimum threshold.
        
        Args:
            reason (str): Reason for shutdown
        """
        if self.is_shutdown:
            if config.ENABLE_ENERGY_DEBUG:
                msg = f"[ENERGY] Node {self.id}: Already shut down (attempted shutdown: {reason})"
                self.log(msg)
                write_log(self, msg)
            return  # Already shut down
        
        self.is_shutdown = True
        self.shutdown_time = self.now
        
        # Change node color to indicate shutdown (dark gray)
        self.scene.nodecolor(self.id, 0.3, 0.3, 0.3)
        
        # Calculate energy statistics
        energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
        total_consumed = self.energy_tx_total + self.energy_rx_total + self.energy_baseline_total
        tx_percent = (self.energy_tx_total / total_consumed * 100) if total_consumed > 0 else 0
        rx_percent = (self.energy_rx_total / total_consumed * 100) if total_consumed > 0 else 0
        baseline_percent = (self.energy_baseline_total / total_consumed * 100) if total_consumed > 0 else 0
        
        # Log shutdown event with detailed statistics
        msg = (f"[ENERGY] Node {self.id}: SHUTDOWN - {reason} "
               f"(energy={self.energy_remaining:.6f}J, {energy_percent:.2f}% remaining, "
               f"consumed={total_consumed:.6f}J: TX={tx_percent:.1f}%, RX={rx_percent:.1f}%, Baseline={baseline_percent:.1f}%, "
               f"lifetime={self.shutdown_time:.1f}s)")
        self.log(msg)
        write_log(self, msg)
        
        # Stop all timers and operations
        # Note: Node will still receive packets but won't process them (checked in on_receive)
    
    ###################
    def check_energy_level(self):
        """Check if node energy is below minimum threshold and shutdown if needed."""
        if not config.ENABLE_ENERGY_MODEL:
            return
        
        if self.energy_remaining < config.BATTERY_ENERGY_MIN and not self.is_shutdown:
            if config.ENABLE_ENERGY_DEBUG:
                energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
                msg = f"[ENERGY] Node {self.id}: Energy check - {self.energy_remaining:.6f}J ({energy_percent:.2f}%) below threshold {config.BATTERY_ENERGY_MIN:.6f}J"
                self.log(msg)
                write_log(self, msg)
            self.shutdown_node(f"Energy below minimum threshold ({config.BATTERY_ENERGY_MIN:.6f}J)")
    
    ###################
    def update_cluster_tx_power(self):
        """Update TX power based on cluster assignment."""
        if self.ch_addr is not None:
            cluster_id = self.ch_addr.net_addr
            self.cluster_tx_power_dbm = get_cluster_tx_power(cluster_id)
            self.tx_power_dbm = self.cluster_tx_power_dbm
            
            if config.ENABLE_ENERGY_DEBUG:
                msg = f"[ENERGY] Node {self.id}: Updated TX power to {self.tx_power_dbm} dBm (cluster {cluster_id})"
                self.log(msg)
                write_log(self, msg)
        else:
            # Use global default
            self.tx_power_dbm = config.TX_POWER_DEFAULT

    ###################
    def route_and_forward_package(self, pck):
        """Routing and forwarding given package.
        Mesh-first routing in local neighborhood, reverts to tree when mesh fails.
        """
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

        # CRITICAL: Broadcast packets should NOT be routed - deliver locally only
        if dest is not None and hasattr(dest, 'is_equal'):
            if dest.is_equal(wsn.BROADCAST_ADDR):
                # Broadcast packets are delivered locally, not routed
                # Don't log every broadcast to avoid spam - only log if routing debug is enabled
                if config.ENABLE_ROUTING_DEBUG:
                    pck['next_hop'] = dest
                    self._record_route(pck, 'LOCAL_BROADCAST', dest)
                # Broadcast packets should be processed locally, not sent again
                # The packet was already received via on_receive, so we just return
                return

        route_trace = pck.setdefault('route_trace', [])
        
        # Add self to route trace first (for new packets)
        if not route_trace or route_trace[-1] != self.id:
            route_trace.append(self.id)
        
        # Loop detection: if packet has visited this node MORE THAN ONCE, drop it
        # (Allow first visit, but detect if we're revisiting)
        visit_count = route_trace.count(self.id)
        if visit_count > 1:
            if config.ENABLE_ROUTING_DEBUG:
                self.log(f"[ROUTING] Node {self.id}: Dropping packet - loop detected (visited {visit_count} times, trace: {route_trace})")
            write_log(self, f"ROUTE_FAIL type={pck.get('type')} reason=loop")
            return
        
        # Limit route trace length to prevent memory issues
        if len(route_trace) > 20:
            if config.ENABLE_ROUTING_DEBUG:
                self.log(f"[ROUTING] Node {self.id}: Dropping packet - too many hops ({len(route_trace)})")
            write_log(self, f"ROUTE_FAIL type={pck.get('type')} reason=too_many_hops")
            return

        # Deliver to self if addressed directly
        # CRITICAL: Don't call self.send() here - packet is already being processed in on_receive()
        # Calling self.send() would broadcast it to neighbors, creating a routing loop
        if self.addr is not None and addr_equals(dest, self.addr):
            pck['next_hop'] = dest
            self._record_route(pck, 'LOCAL_SELF', dest)
            # Packet is already in on_receive(), so just return - don't send it again
            return

        path_str = "UNKNOWN"  # default

        # STEP 1: MESH ROUTING - Check neighbors_table for direct neighbor match
        neighbor_match = next(
            (entry for entry in self.neighbors_table.values() 
             if addr_equals(entry.get('addr'), dest) or addr_equals(entry.get('ch_addr'), dest)),
            None
        )

        # STEP 2: MESH ROUTING - Check multihop_neighbor_table for multi-hop neighbor
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

        # STEP 3: MESH ROUTING - Direct neighbor (1-hop)
        if neighbor_match:
            # CRITICAL: Don't route to ourselves
            if addr_equals(dest, self.addr):
                # Packet is for ourselves - already being processed, don't route
                if config.ENABLE_ROUTING_DEBUG:
                    self.log(f"[ROUTING] Node {self.id}: Mesh routing detected packet for self, not routing")
                return
            
            # Mesh routing if neighbor_hop_count > 1, else direct
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
            else:  # Direct 1-hop neighbor
                pck['next_hop'] = dest
                path_str = "DIRECT"
            
            # CRITICAL: Don't send to ourselves (prevents infinite loop)
            if not addr_equals(pck.get('next_hop'), self.addr):
                self._record_route(pck, path_str, pck['next_hop'])
                self.send(pck)
            return

        # STEP 4: TREE ROUTING - Check if destination is in members_table (cluster member)
        if self.role in (Roles.CLUSTER_HEAD, Roles.ROOT):
            member_match = next(
                (entry for entry in self.members_table if entry == dest),
                None
            )
            if member_match:
                pck['next_hop'] = dest
                path_str = "CLUSTER_MEMBER"
                self._record_route(pck, path_str, dest)
                self.send(pck)
                return

        # STEP 5: TREE ROUTING - Check if destination is in same cluster (route to parent)
        if self.ch_addr is not None and hasattr(dest, 'net_addr'):
            if dest.net_addr == self.ch_addr.net_addr:
                pck['next_hop'] = dest
                path_str = "TREE_SAME_CLUSTER"
                self._record_route(pck, path_str, dest)
                self.send(pck)
                return

        # STEP 6: TREE ROUTING - Check child_networks_table (route to child)
        if self.ch_addr is not None:
            for child_gui, child_networks in self.child_networks_table.items():
                if hasattr(dest, 'net_addr') and dest.net_addr in child_networks:
                    child_info = self.neighbors_table.get(child_gui)
                    if child_info:
                        pck['next_hop'] = child_info.get('addr')
                        path_str = "TREE_CHILD"
                        self._record_route(pck, path_str, pck['next_hop'])
                        self.send(pck)
                        return

        # STEP 7: TREE ROUTING - Send up tree to parent (fallback)
        if self.role != Roles.ROOT and self.parent_gui is not None:
            parent_info = self.neighbors_table.get(self.parent_gui)
            if parent_info:
                pck['next_hop'] = parent_info.get('ch_addr') or parent_info.get('addr')
                path_str = "TREE_PARENT"
                self._record_route(pck, path_str, pck['next_hop'])
                self.send(pck)
                return

        # No route found
        self.debug_log(config.ENABLE_ROUTING_DEBUG, 
                      f"[ROUTING] Node {self.id}: NO_ROUTE for type={pck.get('type')} dest={format_addr(dest)}")
        write_log(self, f"ROUTE_FAIL type={pck.get('type')} dest={format_addr(dest)}")

    ###################
    def _find_direct_neighbor_hop(self, dest):
        if dest is None:
            return None, None
        for gui, info in self.neighbors_table.items():
            if addr_equals(info.get('addr'), dest) or addr_equals(info.get('ch_addr'), dest):
                return dest, f"MESH_DIRECT(gui={gui})"
        return None, None

    ###################
    def _find_multihop_route(self, dest):
        if dest is None:
            return None, None
        for gui, info in self.multihop_neighbor_table.items():
            if addr_equals(info.get('addr'), dest):
                next_gui = info.get('next_hop')
                next_entry = self.neighbors_table.get(next_gui)
                if next_entry:
                    next_addr = next_entry.get('addr')
                    if next_addr is not None:
                        return next_addr, f"MESH_{info.get('hop_dist', 2)}H"
        return None, None

    ###################
    def _find_child_route(self, dest):
        if dest is None or not hasattr(dest, 'net_addr'):
            return None
        target_net = dest.net_addr
        for child_gui, networks in self.child_networks_table.items():
            if target_net in networks:
                child_info = self.neighbors_table.get(child_gui)
                if child_info:
                    return child_info.get('addr')
        return None

    ###################
    def _get_parent_next_hop(self):
        if self.role == Roles.ROOT or self.parent_gui is None:
            return None
        parent_info = self.neighbors_table.get(self.parent_gui)
        if not parent_info:
            return None
        return parent_info.get('addr') or parent_info.get('ch_addr')

    ###################
    def _record_route(self, pck, path_label, next_hop):
        if config.ENABLE_ROUTING_DEBUG:
            msg = f"[ROUTING] Node {self.id}: {path_label} -> dest={format_addr(pck.get('dest'))} next={format_addr(next_hop)}"
            self.log(msg)
            write_log(self, msg)
        log_packet_route(pck, self, format_addr(next_hop), path_label)

    ###################
    def send_network_request(self):
        """Sending network request message to root address to be cluster head

        Args:

        Returns:

        """
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

    ###################
    def send_network_reply(self, dest, addr):
        """Sending network reply message to dest address to be cluster head with a new adress

        Args:
            dest (Addr): destination address
            addr (Addr): cluster head address of new network

        Returns:

        """
        self.route_and_forward_package({'dest': dest, 'type': 'NETWORK_REPLY', 'source': self.addr, 'addr': addr})

    ###################
    def send_network_update(self):
        """Sending network update message to parent

        Args:

        Returns:

        """
        if self.role == Roles.ROOT or self.parent_gui is None:
            return

        parent_addr = self._get_parent_next_hop()
        if parent_addr is None:
            return

        child_networks = [self.ch_addr.net_addr]
        for networks in self.child_networks_table.values():
            child_networks.extend(networks)

        pck = {'dest': parent_addr, 'type': 'NETWORK_UPDATE', 'source': self.addr,
               'gui': self.id, 'child_networks': child_networks}
        self.route_and_forward_package(pck)

    ###################
    def send_random_data_packet(self):
        """Pick a random destination node and trace the routed path."""
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
            'route_trace': [],  # Don't pre-initialize - let route_and_forward_package add self.id
        }
        self.debug_log(config.ENABLE_ROUTING_DEBUG,
                       f"[DATA] Node {self.id}: Sending packet#{packet_id} to ROOT Node {root_node.id}")
        self.route_and_forward_package(pck)

    ###################
    def _init_address_pool(self):
        """Initialize address pool for cluster head - simple and clean."""
        self.node_addr_pool = {i: None for i in range(1, config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER + 1)}
        self.log(f"[CLUSTER_SIZE] Node {self.id}: Initialized address pool with {config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER} slots")
    
    def _assign_child_address(self, child_gui):
        """Assign an address to a child node. Returns address or None if cluster is full."""
        # Search for available address in pool
        for node_addr, assigned_gui in self.node_addr_pool.items():
            if assigned_gui is None or assigned_gui == child_gui:
                # Address available - assign it
                self.node_addr_pool[node_addr] = child_gui
                child_addr = wsn.Addr(self.ch_addr.net_addr, node_addr)
                self.log(f"[CLUSTER_SIZE] Node {self.id}: Assigned address {child_addr} to child {child_gui} (slot {node_addr}/{config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER})")
                return child_addr
        
        # No address available - cluster is full
        self.log(f"[CLUSTER_SIZE] Node {self.id}: CLUSTER FULL! Cannot assign address to child {child_gui}")
        return None

    ###################
    def on_receive(self, pck):
        """Executes when a package received.

        Args:
            pck (Dict): received package
        Returns:

        """
        # Check if node is shut down due to low energy
        if self.is_shutdown:
            if config.ENABLE_ENERGY_DEBUG and pck.get('type') not in ('HEART_BEAT',):  # Don't log every heartbeat
                msg = f"[ENERGY] Node {self.id}: Ignoring {pck.get('type', 'UNKNOWN')} packet - node is shut down"
                self.log(msg)
                write_log(self, msg)
            return
        
        # Ignore packets if node is failed
        if self.is_failed:
            return
        
        # Calculate and deduct RX energy
        if config.ENABLE_ENERGY_MODEL:
            packet_size = estimate_packet_size(pck)
            rx_energy = calculate_rx_energy(packet_size, include_pll_overhead=True)
            
            # Deduct energy
            if self.energy_remaining >= rx_energy:
                self.energy_remaining -= rx_energy
                self.energy_rx_total += rx_energy
                
                if config.ENABLE_ENERGY_DEBUG and pck.get('type') != 'HEART_BEAT':  # Don't log every heartbeat
                    energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
                    msg = f"[ENERGY] Node {self.id}: RX {pck.get('type', 'UNKNOWN')} ({packet_size}B) - {rx_energy*1e6:.3f}µJ, remaining={self.energy_remaining:.6f}J ({energy_percent:.2f}%)"
                    self.log(msg)
                    write_log(self, msg)
            else:
                # Not enough energy - shut down node
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

        if self.role == Roles.ROOT or self.role == Roles.CLUSTER_HEAD:  # if the node is root or cluster head
            # Use safe address comparison
            dest = pck.get('dest')
            
            # CRITICAL: Broadcast packets should NEVER be forwarded - process locally only
            is_broadcast = False
            if dest is not None and hasattr(dest, 'is_equal'):
                is_broadcast = dest.is_equal(wsn.BROADCAST_ADDR)
            
            is_for_self = addr_equals(dest, self.addr) or addr_equals(dest, self.ch_addr)
            
            # Only forward non-broadcast packets that are not for self
            if not is_broadcast and 'next_hop' in pck.keys() and not is_for_self:  # forwards message if destination is not itself
                self.route_and_forward_package(pck)
                return
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'NEIGHBOR_SHARE':
                self.process_neighbor_share(pck)
            if pck['type'] == 'PROBE':  # it waits and sends heart beat message once received probe message
                # yield self.timeout(.5)
                self.send_heart_beat()
            if pck['type'] == 'JOIN_REQUEST':  # it waits and sends join reply message once received join request
                # Check cluster capacity before accepting new child
                child_gui = pck.get('gui')
                
                # CRITICAL: Check if this child already has an address assigned (prevent duplicate processing)
                child_already_assigned = any(assigned_gui == child_gui for assigned_gui in self.node_addr_pool.values())
                if child_already_assigned:
                    # Check if child is already REGISTERED (if so, it shouldn't be sending JOIN_REQUEST)
                    child_node = self._find_node_by_gui(child_gui)
                    if child_node and child_node.role in (Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROUTER):
                        # Child is already registered - ignore this JOIN_REQUEST (shouldn't happen, but prevent loops)
                        if config.ENABLE_CLUSTER_DEBUG:
                            self.log(f"[CLUSTER_SIZE] Node {self.id}: Ignoring JOIN_REQUEST from already-registered child {child_gui} (role={child_node.role})")
                        return
                    
                    # Child already has an address but not registered yet - rate-limited resend
                    # Find the existing address
                    existing_addr = None
                    for node_addr, assigned_gui in self.node_addr_pool.items():
                        if assigned_gui == child_gui:
                            existing_addr = wsn.Addr(self.ch_addr.net_addr, node_addr)
                            break
                    if existing_addr is not None:
                        # Rate limiting: only resend if enough time has passed since last send
                        last_sent = self.join_reply_last_sent.get(child_gui, 0)
                        time_since_last = self.now - last_sent
                        if time_since_last >= self.join_reply_cooldown:
                            # Resend JOIN_REPLY (child might have missed it)
                            self.send_join_reply(child_gui, existing_addr)
                            self.join_reply_last_sent[child_gui] = self.now
                            if config.ENABLE_CLUSTER_DEBUG:
                                self.log(f"[CLUSTER_SIZE] Node {self.id}: Resending JOIN_REPLY to child {child_gui} (already assigned {existing_addr}, cooldown={time_since_last:.1f}s)")
                        # else: silently ignore (rate limited)
                    return  # Don't process again
                
                # Count current children
                current_children = sum(1 for assigned_gui in self.node_addr_pool.values() 
                                     if assigned_gui is not None)
                
                # Check if cluster has reached max allowed children
                if current_children >= config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER:
                    # Cluster is FULL - reject JOIN_REQUEST (no reply sent)
                    self.debug_log(config.ENABLE_CLUSTER_DEBUG,
                                 f"[CLUSTER_SIZE] Node {self.id}: CLUSTER FULL! Cannot accept child {child_gui} "
                                 f"(current={current_children}/{config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER})")
                    # No JOIN_REPLY sent → child will timeout and join another cluster
                else:
                    # Cluster has space - assign address and send JOIN_REPLY
                    child_addr = self._assign_child_address(child_gui)
                    if child_addr is not None:
                        self.send_join_reply(child_gui, child_addr)
                    else:
                        # Should not happen if count is correct, but log for debugging
                        self.log(f"[CLUSTER_SIZE] Node {self.id}: ERROR - Pool allocation failed for child {child_gui}")
            if pck['type'] == 'NETWORK_REQUEST':  # it sends a network reply to requested node
                # yield self.timeout(.5)
                if self.role == Roles.ROOT:
                    # Assign cluster ID from pool
                    cluster_id = None
                    for cid, assigned_source in self.cluster_addr_pool.items():
                        if assigned_source is None or assigned_source == pck['source']:
                            cluster_id = cid
                            self.cluster_addr_pool[cid] = pck['source']
                            break
                    
                    if cluster_id is not None:
                        new_addr = wsn.Addr(cluster_id, 254)
                        request_gui = pck.get('gui')  # Get the requesting node's GUI
                        self.log(f"[CLUSTER_SIZE] ROOT Node {self.id}: Assigned cluster ID {cluster_id} to {pck['source']} (node {request_gui})")
                        # Try to route NETWORK_REPLY back - use reverse route if available
                        route_trace = pck.get('route_trace', [])
                        if route_trace and len(route_trace) > 1:
                            # Use reverse routing: send to the node that forwarded the request
                            prev_hop_gui = route_trace[-2]  # Second-to-last node in trace
                            prev_hop_info = self.neighbors_table.get(prev_hop_gui)
                            if prev_hop_info:
                                # Route through the previous hop
                                reply_pck = {'dest': pck['source'], 'type': 'NETWORK_REPLY', 'source': self.addr, 'addr': new_addr, 'route_trace': [self.id]}
                                reply_pck['next_hop'] = prev_hop_info.get('addr')
                                self._record_route(reply_pck, 'TREE_REVERSE', reply_pck['next_hop'])
                                self.send(reply_pck)
                            else:
                                # Fallback: try normal routing
                                self.send_network_reply(pck['source'], new_addr)
                        else:
                            # No route trace - try normal routing
                            self.send_network_reply(pck['source'], new_addr)
                    else:
                        self.log(f"[CLUSTER_SIZE] ROOT Node {self.id}: ERROR - No available cluster IDs! All {config.NUM_OF_CLUSTERS} clusters in use")
            if pck['type'] == 'JOIN_ACK':
                # Add member to list if within capacity
                member_addr = pck.get('source')
                if member_addr is not None and len(self.members_table) < config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER:
                    # Check if already in members_table to avoid duplicates
                    if member_addr not in self.members_table:
                        self.members_table.append(member_addr)
                        self.log(f"[MEMBER_TABLE] Node {self.id}: Added member {member_addr} (size={len(self.members_table)}/{config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER})")
                        # Trigger CH transfer to reduce overlap (after member joins)
                        # Only for CLUSTER_HEAD (not ROOT) and only if enabled
                        if self.role == Roles.CLUSTER_HEAD and self.ch_transfer_enabled and self.id != ROOT_ID:
                            # Add a small delay to ensure member's heartbeat is received first
                            # Reduced delay to 2 seconds for faster transfer
                            self.set_timer('TIMER_CH_TRANSFER_DELAY', 2)  # Wait 2 seconds for heartbeat
                        else:
                            if config.ENABLE_CLUSTER_DEBUG:
                                self.log(f"[CH_TRANSFER] Node {self.id}: Skipping transfer - role={self.role}, enabled={self.ch_transfer_enabled}, is_root={self.id == ROOT_ID}")
                    else:
                        if config.ENABLE_CLUSTER_DEBUG:
                            self.log(f"[MEMBER_TABLE] Node {self.id}: Member {member_addr} already in table")
                elif member_addr is not None:
                    self.log(f"[MEMBER_TABLE] Node {self.id}: REJECTED {member_addr} - members_table FULL")
            if pck['type'] == 'CH_TRANSFER_ACK':
                # The nominated node accepted the CH role, so we become a router
                # Check if this ACK is for us (destination matches our addr or ch_addr)
                is_for_us = (addr_equals(pck.get('dest'), self.addr) or 
                            addr_equals(pck.get('dest'), self.ch_addr))
                if is_for_us and self.ch_transfer_in_progress and pck.get('gui') == self.ch_transfer_candidate:
                    if config.ENABLE_CLUSTER_DEBUG:
                        self.log(f"[CH_TRANSFER] Node {self.id} received CH_TRANSFER_ACK from {pck.get('gui')}, becoming router")
                        write_log(self, f"[CH_TRANSFER] Node {self.id} received ACK from {pck.get('gui')}, becoming router")
                    self.become_router("CH transfer ACK received")
                    self.ch_transfer_in_progress = False
                    self.ch_transfer_candidate = None
            if pck['type'] == 'NETWORK_UPDATE':
                self.child_networks_table[pck['gui']] = pck['child_networks']
                if self.role != Roles.ROOT:
                    self.send_network_update()
            if pck['type'] == 'SENSOR':
                pass
                # self.log(str(pck['source'])+'--'+str(pck['sensor_value']))

        elif self.role == Roles.REGISTERED:  # if the node is registered
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'NEIGHBOR_SHARE':
                self.process_neighbor_share(pck)
            if pck['type'] == 'PROBE':
                # yield self.timeout(.5)
                self.send_heart_beat()
                # AGGRESSIVE: If we're REGISTERED and haven't received JOIN_REQUEST, become CH immediately
                # This helps isolated UNREGISTERED nodes find a parent
                if getattr(config, 'ENABLE_PROACTIVE_CH_CREATION', True):
                    if len(self.received_JR_guis) == 0 and self.ch_addr is None:
                        # Check if we've been REGISTERED for at least a few seconds
                        if self.registered_since is not None and (self.now - self.registered_since) >= 5:
                            self.log(f"[CH_CREATION] Node {self.id}: Received PROBE from {pck.get('gui')}, becoming CH immediately (no JOIN_REQUEST received)")
                            write_log(self, f"[CH_CREATION] Node {self.id}: Becoming CLUSTER_HEAD proactively after receiving PROBE")
                            
                            # Self-assign a temporary cluster address (will be updated when ROOT responds)
                            temp_cluster_id = (self.id % (config.NUM_OF_CLUSTERS - 1)) + 1  # Avoid 0 and 255
                            self.ch_addr = wsn.Addr(temp_cluster_id, 254)
                            self.set_role(Roles.CLUSTER_HEAD, reason="proactive CH creation from PROBE")
                            self._init_address_pool()
                            
                            # Send heartbeats immediately so UNREGISTERED nodes can discover us
                            self.send_heart_beat()
                            if not hasattr(self, 'heartbeat_timer_active') or not self.heartbeat_timer_active:
                                self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                                self.heartbeat_timer_active = True
                            
                            # Still send NETWORK_REQUEST to ROOT to get official cluster address
                            self.send_network_request()
                            
                            # Start neighbor sharing if enabled
                            if config.ENABLE_MULTIHOP_DISCOVERY:
                                self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)
            if pck['type'] == 'JOIN_REQUEST':  # it sends a network request to the root
                # CRITICAL FIX: REGISTERED nodes should forward JOIN_REQUEST to their parent
                # OR immediately become CLUSTER_HEAD to accept children
                # Avoid duplicates in received_JR_guis
                if pck['gui'] not in self.received_JR_guis:
                    self.received_JR_guis.append(pck['gui'])
                    if self.ch_addr is None:
                        # CRITICAL FIX: REGISTERED nodes should become CLUSTER_HEAD immediately
                        # Don't wait for ROOT's NETWORK_REPLY - become CH proactively to accept children
                        # This is especially important for nodes that are far from ROOT but close to UNREGISTERED nodes
                        write_log(self, f"[CH_CREATION] Node {self.id}: Received JOIN_REQUEST from {pck['gui']}, becoming CLUSTER_HEAD immediately (self-assigning cluster address)")
                        
                        # Self-assign a temporary cluster address (will be updated when ROOT responds)
                        # Use a unique cluster ID based on node ID to avoid conflicts
                        temp_cluster_id = (self.id % (config.NUM_OF_CLUSTERS - 1)) + 1  # Avoid 0 and 255
                        self.ch_addr = wsn.Addr(temp_cluster_id, 254)
                        self.set_role(Roles.CLUSTER_HEAD, reason="immediate CH creation for JOIN_REQUEST")
                        self._init_address_pool()
                        
                        # Send heartbeats immediately so other UNREGISTERED nodes can discover us
                        self.send_heart_beat()
                        if not hasattr(self, 'heartbeat_timer_active') or not self.heartbeat_timer_active:
                            self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                            self.heartbeat_timer_active = True
                        
                        # Start neighbor sharing if enabled
                        if config.ENABLE_MULTIHOP_DISCOVERY:
                            self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)
                        
                        # Still send NETWORK_REQUEST to ROOT to get official cluster address
                        # ROOT will assign a proper cluster ID in NETWORK_REPLY
                        self.send_network_request()
                        
                        # Now we can accept the child immediately
                        child_gui = pck['gui']
                        child_addr = self._assign_child_address(child_gui)
                        if child_addr is not None:
                            self.send_join_reply(child_gui, child_addr)
                            write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Sent JOIN_REPLY to child {child_gui} (addr={format_addr(child_addr)}) immediately after becoming CH")
                        else:
                            write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Cluster full, cannot accept child {child_gui}")
                    else:
                        # Already a CH - can send JOIN_REPLY directly
                        # Process this JOIN_REQUEST immediately
                        child_gui = pck['gui']
                        child_addr = self._assign_child_address(child_gui)
                        if child_addr is not None:
                            self.send_join_reply(child_gui, child_addr)
                            write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Sent JOIN_REPLY to child {child_gui} (addr={format_addr(child_addr)})")
                        else:
                            write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Cluster full, cannot accept child {child_gui}")
            if pck['type'] == 'TRIGGER_CH_CREATION':  # Request from UNREGISTERED node to become CH
                # Check if this trigger is for us (either no target_gui specified, or target_gui matches our id)
                target_gui = pck.get('target_gui')
                if target_gui is None or target_gui == self.id:
                    # Only respond if we haven't received JOIN_REQUEST and haven't become CH yet
                    if len(self.received_JR_guis) == 0 and self.ch_addr is None:
                        self.log(f"[CH_CREATION] Node {self.id}: Received TRIGGER_CH_CREATION from {pck.get('gui')}, becoming cluster head")
                        self.send_network_request()
                    else:
                        if config.ENABLE_CLUSTER_DEBUG:
                            self.log(f"[CH_CREATION] Node {self.id}: Ignored TRIGGER_CH_CREATION - already has JOIN_REQUEST ({len(self.received_JR_guis)}) or CH address ({self.ch_addr})")
            if pck['type'] == 'NETWORK_REPLY':  # it becomes cluster head and send join reply to the candidates
                # If we already have a ch_addr (self-assigned), update it with ROOT's official address
                if self.ch_addr is not None:
                    old_ch_addr = self.ch_addr
                    self.ch_addr = pck['addr']  # Update with ROOT's official cluster address
                    write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Updated cluster address from {format_addr(old_ch_addr)} to {format_addr(self.ch_addr)} (ROOT's official assignment)")
                    # Update all child addresses to use new cluster address
                    for node_addr, child_gui in list(self.node_addr_pool.items()):
                        if child_gui is not None:
                            # Resend JOIN_REPLY with updated address
                            new_child_addr = wsn.Addr(self.ch_addr.net_addr, node_addr)
                            self.send_join_reply(child_gui, new_child_addr)
                            write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Resent JOIN_REPLY to child {child_gui} with updated address {format_addr(new_child_addr)}")
                    return
                
                # First time becoming CH (normal flow)
                self.members_table = []
                self.ch_addr = pck['addr']  # Set ch_addr before set_role so TX range is drawn correctly
                
                # Set TX power for this cluster (if not using global power)
                if not config.USE_GLOBAL_TX_POWER:
                    cluster_id = self.ch_addr.net_addr
                    # Assign TX power to cluster (can be optimized later)
                    # For now, use default or optimize based on cluster size/distance
                    if cluster_id not in CLUSTER_TX_POWER:
                        # Default: use maximum power for reliability
                        # Can be optimized by cluster optimization protocol
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
                
                self.set_role(Roles.CLUSTER_HEAD)  # This will set color and draw TX range
                try:
                    write_clusterhead_distances_csv("clusterhead_distances.csv")
                except Exception as e:
                    self.log(f"CH CSV export error: {e}")
                
                # Initialize address pool for new CLUSTER_HEAD
                self._init_address_pool()
                
                self.send_network_update()
                # yield self.timeout(.5)
                self.send_heart_beat()
                # Start neighbor sharing for CLUSTER_HEAD
                if config.ENABLE_MULTIHOP_DISCOVERY:
                    self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)
                
                # Process pending join requests (up to max allowed children)
                write_log(self, f"[CLUSTER_SIZE] Node {self.id}: Processing {len(self.received_JR_guis)} pending join requests")
                accepted_count = 0
                rejected_count = 0
                
                for gui in self.received_JR_guis:
                    # CRITICAL: Check if this child already has an address assigned (prevent duplicate processing)
                    child_already_assigned = any(assigned_gui == gui for assigned_gui in self.node_addr_pool.values())
                    if child_already_assigned:
                        # Child already processed - skip
                        if config.ENABLE_CLUSTER_DEBUG:
                            self.log(f"[CLUSTER_SIZE] Node {self.id}: Skipping pending child {gui} - already assigned")
                        continue
                    
                    # Check if we've reached max allowed children
                    current_children = sum(1 for assigned_gui in self.node_addr_pool.values() 
                                         if assigned_gui is not None)
                    
                    if current_children >= config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER:
                        # Cluster is full - reject remaining requests
                        rejected_count += 1
                        self.debug_log(config.ENABLE_CLUSTER_DEBUG,
                                     f"[CLUSTER_SIZE] Node {self.id}: REJECTED pending child {gui} - cluster full "
                                     f"({current_children}/{config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER})")
                    else:
                        # Accept child
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
            if pck['type'] == 'CH_TRANSFER':  # Received CH role transfer offer
                # Accept the CH role transfer
                if self.id != ROOT_ID and self.role == Roles.REGISTERED:
                    new_ch_addr = pck.get('new_ch_addr') or pck.get('prev_ch_addr')
                    if new_ch_addr is not None:
                        self.log(f"[CH_TRANSFER] Node {self.id} accepting CH role transfer from {pck.get('gui')}")
                        write_log(self, f"[CH_TRANSFER] Node {self.id} accepting CH role from {pck.get('gui')}")
                        
                        # Become CLUSTER_HEAD with the new address
                        self.set_role(Roles.CLUSTER_HEAD, reason="received CH transfer")
                        self.ch_addr = new_ch_addr
                        
                        # Initialize address pool if it exists
                        if hasattr(self, '_init_address_pool'):
                            self._init_address_pool()
                        
                        # Start CH operations
                        self.send_network_update()
                        self.send_heart_beat()
                        self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                        
                        # Start neighbor sharing if enabled
                        if getattr(config, 'ENABLE_MULTIHOP_DISCOVERY', False):
                            self.set_timer('TIMER_NEIGHBOR_SHARE', getattr(config, 'NEIGHBOR_SHARE_INTERVAL', 30))
                        
                        # Send ACK back to previous CH
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

        elif self.role == Roles.UNDISCOVERED:  # if the node is undiscovered
            if pck['type'] == 'HEART_BEAT':  # it kills probe timer, becomes unregistered and sets join request timer once received heart beat
                self.update_neighbor(pck)
                self.kill_timer('TIMER_PROBE')
                self.become_unregistered()

        if self.role == Roles.UNREGISTERED:  # if the node is unregistered
            if pck['type'] == 'HEART_BEAT':
                # Debug: Log received heartbeat to see what we're getting
                sender_gui = pck.get('gui')
                sender_role = pck.get('role')
                sender_addr = pck.get('addr') or pck.get('source') or pck.get('ch_addr')
                # Always log if we have no candidates (helps debug why nodes can't join)
                if len(self.candidate_parents_table) == 0:
                    write_log(self, f"[JOIN] Node {self.id}: Received HEART_BEAT from {sender_gui} (role={sender_role}, addr={format_addr(sender_addr)})")
                self.update_neighbor(pck)
            if pck['type'] == 'NEIGHBOR_SHARE':
                self.process_neighbor_share(pck)
            if pck['type'] == 'JOIN_REPLY':  # it becomes registered and sends join ack if the message is sent to itself once received join reply
                if pck['dest_gui'] == self.id:
                    self.addr = pck['addr']
                    self.parent_gui = pck['gui']
                    self.root_addr = pck['root_addr']
                    self.hop_count = pck['hop_count']
                    self.registered_time = self.now
                    if self.wake_up_time is not None:
                        log_registration_time(self.id, self.wake_up_time, self.registered_time)
                    self.draw_parent()
                    self.kill_timer('TIMER_JOIN_REQUEST')
                    
                    # Update TX power based on cluster assignment
                    if self.addr is not None:
                        self.update_cluster_tx_power()
                    
                    self.send_heart_beat()
                    self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                    self.send_join_ack(pck['source'])
                    if self.ch_addr is not None: # it could be a cluster head which lost its parent
                        self.set_role(Roles.CLUSTER_HEAD)  # This will set color and draw TX range
                        self.send_network_update()
                    else:
                        self.set_role(Roles.REGISTERED)  # This will set color
                        self.registered_since = self.now  # Track when we became REGISTERED
                        # Start periodic neighbor sharing
                        if config.ENABLE_MULTIHOP_DISCOVERY:
                            self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)
                        self.set_timer('TIMER_SENSOR', max(1, config.DATA_PACKET_INTERVAL))
                        # Set timer for proactive CH creation if enabled
                        if getattr(config, 'ENABLE_PROACTIVE_CH_CREATION', True):
                            proactive_timer = getattr(config, 'PROACTIVE_CH_TIMER', 60)
                            self.set_timer('TIMER_PROACTIVE_CH', proactive_timer)
                    
                    # Start baseline energy consumption timer
                    if config.ENABLE_ENERGY_MODEL:
                        self.set_timer('TIMER_BASELINE_ENERGY', 1.0)  # Check every second
                    # # sensor implementation
                    # timer_duration =  self.id % 20
                    # if timer_duration == 0: timer_duration = 1
                    # self.set_timer('TIMER_SENSOR', timer_duration)
            if pck['type'] == 'CH_TRANSFER':  # REGISTERED node can also receive CH transfer
                # Accept the CH role transfer
                if self.id != ROOT_ID and self.role == Roles.REGISTERED:
                    new_ch_addr = pck.get('new_ch_addr') or pck.get('prev_ch_addr')
                    if new_ch_addr is not None:
                        self.log(f"[CH_TRANSFER] Node {self.id} accepting CH role transfer from {pck.get('gui')}")
                        write_log(self, f"[CH_TRANSFER] Node {self.id} accepting CH role from {pck.get('gui')}")
                        
                        # Become CLUSTER_HEAD with the new address
                        self.set_role(Roles.CLUSTER_HEAD, reason="received CH transfer")
                        self.ch_addr = new_ch_addr
                        
                        # Initialize address pool if it exists
                        if hasattr(self, '_init_address_pool'):
                            self._init_address_pool()
                        
                        # Start CH operations
                        self.send_network_update()
                        self.send_heart_beat()
                        self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                        
                        # Start neighbor sharing if enabled
                        if getattr(config, 'ENABLE_MULTIHOP_DISCOVERY', False):
                            self.set_timer('TIMER_NEIGHBOR_SHARE', getattr(config, 'NEIGHBOR_SHARE_INTERVAL', 30))
                        
                        # Send ACK back to previous CH
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

        elif self.role == Roles.ROUTER:  # Router acts as bridge between CHs
            # Use safe address comparison (routers have ch_addr=None)
            dest = pck.get('dest')
            
            # CRITICAL: Broadcast packets should NEVER be forwarded - process locally only
            is_broadcast = False
            if dest is not None and hasattr(dest, 'is_equal'):
                is_broadcast = dest.is_equal(wsn.BROADCAST_ADDR)
            
            is_for_self = addr_equals(dest, self.addr) or addr_equals(dest, self.ch_addr)
            
            # Forward packets if not destined for self and not broadcast (routers don't accept JOIN_REQUEST, etc.)
            if not is_broadcast and not is_for_self:
                # If packet already has next_hop, forward it
                if 'next_hop' in pck.keys():
                    self.route_and_forward_package(pck)
                    return
                # Otherwise, route it first (for packets without next_hop yet)
                else:
                    self.route_and_forward_package(pck)
                    return
            
            # Only process packets destined for this router
            # Maintain neighbor table for routing
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'NEIGHBOR_SHARE':
                self.process_neighbor_share(pck)
            if pck['type'] == 'PROBE':
                self.send_heart_beat()
            
            # Accept network updates to maintain routing table
            if pck['type'] == 'NETWORK_UPDATE':
                self.child_networks_table[pck['gui']] = pck['child_networks']

    ###################
    def on_timer_fired(self, name, *args, **kwargs):
        """Executes when a timer fired.

        Args:
            name (string): Name of timer.
            *args (string): Additional args.
            **kwargs (string): Additional key word args.
        Returns:

        """
        if name == 'TIMER_ARRIVAL':  # it wakes up and set timer probe once time arrival timer fired
            self.scene.nodecolor(self.id, 1, 0, 0)  # sets self color to red
            self.wake_up()
            self.wake_up_time = self.now
            self.set_timer('TIMER_PROBE', 1)

        elif name == 'TIMER_PROBE':  # it sends probe if counter didn't reach the threshold once timer probe fired.
            if self.c_probe < self.th_probe:
                self.send_probe()
                self.c_probe += 1
                self.set_timer('TIMER_PROBE', 1)
            else:  # if the counter reached the threshold
                if self.is_root_eligible:  # if the node is root eligible, it becomes root
                    self.members_table = []
                    self.addr = wsn.Addr(0, 254)  # ROOT uses net_addr=0
                    self.ch_addr = wsn.Addr(0, 254)
                    self.root_addr = self.addr
                    self.hop_count = 0
                    self.set_role(Roles.ROOT)  # This will draw TX range and set color
                    
                    # Initialize address pools for ROOT
                    self._init_address_pool()  # For direct children
                    self.cluster_addr_pool = {i: None for i in range(1, config.NUM_OF_CLUSTERS + 1)}  # For cluster IDs (start from 1, ROOT uses net_addr=0)
                    self.log(f"[CLUSTER_SIZE] ROOT Node {self.id}: Initialized pools - {config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER} child slots, {config.NUM_OF_CLUSTERS} cluster IDs (ROOT uses net_addr=0)")
                    
                    self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                    # Start neighbor sharing for ROOT
                    if config.ENABLE_MULTIHOP_DISCOVERY:
                        self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)
                    
                    # Start cluster optimization timer (ROOT coordinates optimization)
                    if config.ENABLE_CLUSTER_OPTIMIZATION:
                        self.set_timer('TIMER_CLUSTER_OPTIMIZATION', config.CLUSTER_OPTIMIZATION_INTERVAL)
                    
                    # Start baseline energy consumption timer
                    if config.ENABLE_ENERGY_MODEL:
                        self.set_timer('TIMER_BASELINE_ENERGY', 1.0)
                else:  # otherwise it keeps trying to sending probe after a long time
                    # Don't become UNREGISTERED too early - let nodes stay UNDISCOVERED longer
                    # Only become UNREGISTERED if we've been trying for a while and have no neighbors
                    if self.role == Roles.UNDISCOVERED and len(self.neighbors_table) == 0:
                        # Only become UNREGISTERED if we've been probing for a while (e.g., 30+ seconds)
                        # This gives nodes time to discover neighbors before giving up
                        if self.now > 30:  # Only after 30 seconds of simulation time
                            self.become_unregistered()
                    self.c_probe = 0
                    # Keep probing periodically to maintain simulation activity
                    self.set_timer('TIMER_PROBE', 30)
                    # Also keep trying to join (for both UNDISCOVERED and UNREGISTERED)
                    if self.role in (Roles.UNDISCOVERED, Roles.UNREGISTERED):
                        self.set_timer('TIMER_JOIN_REQUEST', 20)

        elif name == 'TIMER_HEART_BEAT':  # it sends heart beat message once heart beat timer fired
            self.send_heart_beat()
            self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
            # Mark heartbeat timer as active for ROUTER nodes
            if self.role == Roles.ROUTER:
                self.heartbeat_timer_active = True
            #print(self.id)
        
        elif name == 'TIMER_BASELINE_ENERGY':  # Baseline energy consumption (idle/sleep power)
            if config.ENABLE_ENERGY_MODEL and not self.is_shutdown:
                # Calculate baseline energy consumption for 1 second
                # P = V × I_base, E = P × t
                baseline_power = config.CC2420_VOLTAGE * config.BASELINE_CURRENT  # Watts
                baseline_energy = baseline_power * 1.0  # Joules (for 1 second)
                
                # Deduct baseline energy
                if self.energy_remaining >= baseline_energy:
                    self.energy_remaining -= baseline_energy
                    self.energy_baseline_total += baseline_energy
                    
                    # Debug: Log baseline energy consumption periodically (every 10 seconds to avoid spam)
                    if config.ENABLE_ENERGY_DEBUG and int(self.now) % 10 == 0:
                        energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
                        msg = f"[ENERGY] Node {self.id}: Baseline - {baseline_energy*1e6:.3f}µJ, remaining={self.energy_remaining:.6f}J ({energy_percent:.2f}%)"
                        self.log(msg)
                        write_log(self, msg)
                else:
                    # Not enough energy - shut down
                    self.energy_remaining = 0.0
                    self.shutdown_node("Insufficient energy for baseline operation")
                    return
                
                # Check if energy is below minimum threshold
                self.check_energy_level()
                
                # Warn if energy is getting low (below 10% but above minimum)
                if config.ENABLE_ENERGY_DEBUG:
                    energy_percent = (self.energy_remaining / config.BATTERY_ENERGY_TOTAL) * 100
                    if energy_percent < 10.0 and energy_percent >= (config.BATTERY_ENERGY_MIN / config.BATTERY_ENERGY_TOTAL * 100):
                        # Log warning every 5 seconds to avoid spam
                        if int(self.now) % 5 == 0:
                            msg = f"[ENERGY] Node {self.id}: WARNING - Low energy: {self.energy_remaining:.6f}J ({energy_percent:.2f}%)"
                            self.log(msg)
                            write_log(self, msg)
                
                # Reschedule timer
                self.set_timer('TIMER_BASELINE_ENERGY', 1.0)
 
        elif name == 'TIMER_NEIGHBOR_SHARE':  # Periodic neighbor info sharing
            if config.ENABLE_MULTIHOP_DISCOVERY:
                self.share_neighbor_info()
                self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)

        elif name == 'TIMER_JOIN_REQUEST':  # if it has not received heart beat messages before, it sets timer again and wait heart beat messages once join request timer fired.
            if len(self.candidate_parents_table) == 0:
                # No candidates yet - keep probing and retry
                self.send_probe()
                self.failed_join_attempts += 1
                
                # Log why we have no candidates (for debugging)
                if config.ENABLE_CLUSTER_DEBUG and self.failed_join_attempts % 10 == 0:
                    total_neighbors = len(self.neighbors_table)
                    valid_parents = sum(1 for n in self.neighbors_table.values() 
                                      if n.get('role') in (Roles.CLUSTER_HEAD, Roles.ROUTER, Roles.ROOT))
                    self.log(f"[JOIN] Node {self.id}: No candidates - total neighbors={total_neighbors}, valid parents={valid_parents}, failed attempts={self.failed_join_attempts}")
                
                # Only trigger CH creation once per threshold, not every time
                threshold = getattr(config, 'UNREGISTERED_CH_TRIGGER_THRESHOLD', 3)
                if self.failed_join_attempts >= threshold and (self.failed_join_attempts % threshold == 0):
                    # Only trigger every threshold attempts to prevent spam
                    self.log(f"[CH_CREATION] Node {self.id}: {self.failed_join_attempts} failed attempts - triggering CH creation")
                    self._trigger_ch_creation()
                
                self.set_timer('TIMER_JOIN_REQUEST', 20)  # Retry after 20 seconds
                if config.ENABLE_CLUSTER_DEBUG and self.failed_join_attempts % 5 == 0:
                    self.log(f"[JOIN] Node {self.id}: No candidates, retrying probe and join request (failed attempts={self.failed_join_attempts})")
            else:  # otherwise it chose one of them and sends join request
                # Only send JOIN_REQUEST if not already registered
                if self.role not in (Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROUTER, Roles.ROOT):
                    # Check rate limit before calling select_and_join
                    if self.last_join_request_sent_time is not None:
                        time_since_last = self.now - self.last_join_request_sent_time
                        # Add small epsilon to prevent floating point issues
                        if time_since_last < (self.join_request_cooldown - 0.0001):
                            # Still in cooldown - reschedule for when cooldown expires
                            remaining_cooldown = self.join_request_cooldown - time_since_last
                            # Ensure minimum delay to prevent negative delay error (set_timer subtracts 0.00001)
                            if remaining_cooldown < 0.0001:
                                remaining_cooldown = 0.0001
                            self.set_timer('TIMER_JOIN_REQUEST', remaining_cooldown)
                            if config.ENABLE_CLUSTER_DEBUG:
                                write_log(self, f"[JOIN] Node {self.id}: Rate limiting JOIN_REQUEST (last sent {time_since_last:.1f}s ago, rescheduling in {remaining_cooldown:.1f}s)")
                            return  # Exit early, timer already rescheduled
                    
                    # Rate limit passed - try to join
                    # Store time before calling select_and_join to check if a request was actually sent
                    time_before = self.last_join_request_sent_time
                    self.select_and_join()
                    # Reschedule timer for next attempt
                    # If last_join_request_sent_time changed, a request was sent - use cooldown
                    # Otherwise, no request was sent (no candidates) - reschedule sooner
                    if self.last_join_request_sent_time is not None and self.last_join_request_sent_time != time_before:
                        # A request was just sent - schedule next attempt after cooldown
                        self.set_timer('TIMER_JOIN_REQUEST', self.join_request_cooldown)
                    else:
                        # No request was sent (maybe no candidates) - reschedule sooner to retry
                        self.set_timer('TIMER_JOIN_REQUEST', 20)
                else:
                    # Already registered - still reschedule to keep simulation running
                    self.set_timer('TIMER_JOIN_REQUEST', 60)  # Check periodically even if registered

        elif name == 'TIMER_CH_TRANSFER_DELAY':
            # Trigger CH transfer after a delay to ensure member heartbeats are received
            if self.role == Roles.CLUSTER_HEAD and self.ch_transfer_enabled and self.id != ROOT_ID:
                if config.ENABLE_CLUSTER_DEBUG:
                    self.log(f"[CH_TRANSFER] Node {self.id}: TIMER_CH_TRANSFER_DELAY fired, initiating transfer (members={len(self.members_table)})")
                self.initiate_ch_transfer()
            else:
                if config.ENABLE_CLUSTER_DEBUG:
                    self.log(f"[CH_TRANSFER] Node {self.id}: TIMER_CH_TRANSFER_DELAY fired but conditions not met (role={self.role}, enabled={self.ch_transfer_enabled}, is_root={self.id == ROOT_ID})")
        
        elif name == 'TIMER_PROACTIVE_CH':
            # Proactive CH creation: REGISTERED node becomes CH if no JOIN_REQUEST received
            proactive_timer = getattr(config, 'PROACTIVE_CH_TIMER', 15)
            if self.role == Roles.REGISTERED and getattr(config, 'ENABLE_PROACTIVE_CH_CREATION', True):
                if len(self.received_JR_guis) == 0 and self.ch_addr is None:
                    self.log(f"[CH_CREATION] Node {self.id}: Proactive CH creation - no JOIN_REQUEST received after {proactive_timer}s, becoming cluster head")
                    self.send_network_request()
                else:
                    if config.ENABLE_CLUSTER_DEBUG:
                        self.log(f"[CH_CREATION] Node {self.id}: Proactive CH timer fired but already has JOIN_REQUEST ({len(self.received_JR_guis)}) or CH address ({self.ch_addr})")
            # Reschedule timer
            self.set_timer('TIMER_PROACTIVE_CH', proactive_timer)
        
        elif name == 'TIMER_CLUSTER_OPTIMIZATION':
            # Cluster optimization: Run periodically to minimize clusters or energy
            if self.role == Roles.ROOT and config.ENABLE_CLUSTER_OPTIMIZATION:
                optimize_clusters()
                # Reschedule
                self.set_timer('TIMER_CLUSTER_OPTIMIZATION', config.CLUSTER_OPTIMIZATION_INTERVAL)

        elif name == 'TIMER_SENSOR':
            self.send_random_data_packet()
            interval = max(1, config.DATA_PACKET_INTERVAL)
            self.set_timer('TIMER_SENSOR', interval)
        elif name == 'TIMER_EXPORT_CH_CSV':
            # Only root should drive exports (cheap guard)
            if self.role == Roles.ROOT:
                write_clusterhead_distances_csv("clusterhead_distances.csv")
                # reschedule
                self.set_timer('TIMER_EXPORT_CH_CSV', config.EXPORT_CH_CSV_INTERVAL)
        elif name == 'TIMER_EXPORT_NEIGHBOR_CSV':
            if self.role == Roles.ROOT:
                write_neighbor_distances_csv("neighbor_distances.csv")
                self.set_timer('TIMER_EXPORT_NEIGHBOR_CSV', config.EXPORT_NEIGHBOR_CSV_INTERVAL)

        elif name.startswith('TIMER_NODE_FAILURE_'):
            # Node failure event
            self.fail_node()
            # Schedule recovery
            for recovery_time, node_id, failure_time in SCHEDULED_RECOVERIES:
                if node_id == self.id:
                    recovery_delay = recovery_time - self.sim.now
                    self.set_timer(f'TIMER_NODE_RECOVERY_{self.id}', recovery_delay)
                    break
        
        elif name.startswith('TIMER_NODE_RECOVERY_'):
            # Node recovery event
            self.recover_node()



ROOT_ID = 1 # 0..count-1



def write_node_distances_csv(path="node_distances.csv"):
    """Write pairwise node-to-node Euclidean distances as an edge list."""
    ids = sorted(NODE_POS.keys())
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "target_id", "distance"])
        for i, sid in enumerate(ids):
            x1, y1 = NODE_POS[sid]
            for tid in ids[i+1:]:  # i+1 to avoid duplicates and self-pairs
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
    """Write pairwise distances between current cluster heads."""
    clusterheads = []
    for node in sim.nodes:
        # Only collect nodes that are cluster heads and have recorded positions
        if hasattr(node, "role") and node.role == Roles.CLUSTER_HEAD and node.id in NODE_POS:
            x, y = NODE_POS[node.id]
            clusterheads.append((node.id, x, y))

    if len(clusterheads) < 2:
        # Still write the header so the file exists/is refreshed
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
    """
    Export neighbor distances per node.
    Each row is (node -> neighbor) with distance from NODE_POS.

    Args:
        path (str): output CSV path
        dedupe_undirected (bool): if True, writes each unordered pair once
                                  (min(node_id,neighbor_id), max(...)).
                                  If False, writes one row per direction.
    """
    # Safety: ensure we can compute distances
    if not globals().get("NODE_POS"):
        raise RuntimeError("NODE_POS is missing; record positions during create_network().")

    # Prepare a set to avoid duplicates if dedupe_undirected=True
    seen_pairs = set()

    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "neighbor_id", "distance",
                    "neighbor_role", "neighbor_hop_count", "arrival_time"])

        for node in sim.nodes:
            # Skip nodes without any neighbor info yet
            if not hasattr(node, "neighbors_table"):
                continue

            x1, y1 = NODE_POS.get(node.id, (None, None))
            if x1 is None:
                continue  # no position → cannot compute distance

            # neighbors_table: key = neighbor GUI, value = heartbeat packet dict
            for n_gui, pck in getattr(node, "neighbors_table", {}).items():
                # Optional dedupe (unordered)
                if dedupe_undirected:
                    key = (min(node.id, n_gui), max(node.id, n_gui))
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)

                # Position of neighbor
                x2, y2 = NODE_POS.get(n_gui, (None, None))
                if x2 is None:
                    continue

                # Distance (prefer pck['distance'] if you added it in update_neighbor)
                dist = pck.get("distance")
                if dist is None:
                    dist = math.hypot(x1 - x2, y1 - y2)

                # Extra fields (best-effort; may be missing)
                n_role = getattr(pck.get("role", None), "name", pck.get("role", None))
                hop = pck.get("hop_count", "")
                at  = pck.get("arrival_time", "")

                w.writerow([node.id, n_gui, f"{dist:.6f}", n_role, hop, at])


def write_multihop_neighbor_table_csv(path="multihop_neighbor_table.csv"):
    """Export multihop neighbor table for all nodes"""
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

###########################################################
def create_network(node_class, number_of_nodes=100):
    """Creates given number of nodes at random positions with random arrival times.

    Args:
        node_class (Class): Node class to be created.
        number_of_nodes (int): Number of nodes.
    Returns:

    """
    edge = math.ceil(math.sqrt(number_of_nodes))
    for i in range(number_of_nodes):
        x = i / edge
        y = i % edge
        px = 300 + config.SCALE*x * config.SIM_NODE_PLACING_CELL_SIZE + random.uniform(-1 * config.SIM_NODE_PLACING_CELL_SIZE / 3, config.SIM_NODE_PLACING_CELL_SIZE / 3)
        py = 200 + config.SCALE* y * config.SIM_NODE_PLACING_CELL_SIZE + random.uniform(-1 * config.SIM_NODE_PLACING_CELL_SIZE / 3, config.SIM_NODE_PLACING_CELL_SIZE / 3)
        node = sim.add_node(node_class, (px, py))
        NODE_POS[node.id] = (px, py)   # <— add this line
        ALL_NODES.append(node)
        node.tx_range = config.NODE_TX_RANGE * config.SCALE
        node.logging = True
        node.arrival = random.uniform(0, config.NODE_ARRIVAL_MAX)
        if node.id == ROOT_ID:
            node.arrival = 0.1


init_log_file()

# Set random seed for reproducible simulations
random.seed(getattr(config, 'SIM_SEED', 42))
log_to_console_and_file(f"🎲 Using random seed: {getattr(config, 'SIM_SEED', 42)}")

sim = wsn.Simulator(
    duration=config.SIM_DURATION,
    timescale=config.SIM_TIME_SCALE,
    visual=config.SIM_VISUALIZATION,
    terrain_size=config.SIM_TERRAIN_SIZE,
    title=config.SIM_TITLE,
    seed=getattr(config, 'SIM_SEED', 42))

# creating random network
create_network(SensorNode, config.SIM_NODE_COUNT)

write_node_distances_csv("node_distances.csv")
write_node_distance_matrix_csv("node_distance_matrix.csv")

# Schedule random node failures if enabled
if config.ENABLE_NODE_FAILURE_RECOVERY:
    # Eligible nodes: not ROOT, and prefer nodes that will likely be registered by failure time
    # We'll pick any non-root node for now, and they'll only fail if registered
    eligible_nodes = [n for n in ALL_NODES if n.id != ROOT_ID]
    if len(eligible_nodes) >= config.NUM_NODES_TO_FAIL:
        selected_nodes = random.sample(eligible_nodes, config.NUM_NODES_TO_FAIL)
        for i, node in enumerate(selected_nodes):
            failure_time = config.NODE_FAILURE_START_TIME + i * config.NODE_FAILURE_INTERVAL
            recovery_time = failure_time + random.uniform(config.NODE_RECOVERY_TIME_MIN, 
                                                          config.NODE_RECOVERY_TIME_MAX)
            
            # Store failure schedule for node to handle
            SCHEDULED_FAILURES.append((failure_time, node.id))
            SCHEDULED_RECOVERIES.append((recovery_time, node.id, failure_time))
            
            # Schedule the failure timer on the node
            node.set_timer(f'TIMER_NODE_FAILURE_{node.id}', failure_time)
            
            msg = f"📅 Scheduled: Node {node.id} will fail at {failure_time:.1f}s, recover at {recovery_time:.1f}s (downtime: {recovery_time-failure_time:.1f}s)"
            log_to_console_and_file(msg)

# start the simulation
sim.run()
log_to_console_and_file("Simulation Finished")

# Export multihop neighbor table if enabled
if config.ENABLE_MULTIHOP_DISCOVERY:
    write_multihop_neighbor_table_csv("multihop_neighbor_table.csv")

calculate_and_log_average_join_time()
calculate_and_log_average_packet_delay()
if config.ENABLE_NODE_FAILURE_RECOVERY:
    calculate_and_log_recovery_statistics()
log_packet_loss_statistics()

# Close log file AFTER all statistics are written
close_log_file()


# Created 100 nodes at random locations with random arrival times.
# When nodes are created they appear in white
# Activated nodes becomes red
# Discovered nodes will be yellow
# Registered nodes will be green.
# Root node will be black.
# Routers/Cluster Heads should be blue
