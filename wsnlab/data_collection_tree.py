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


Roles = Enum('Roles', 'UNDISCOVERED UNREGISTERED ROOT REGISTERED CLUSTER_HEAD')
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
        self.cluster_addr_pool = {}  # {cluster_id: source or None} - pool of cluster IDs (ROOT only)
        
        # Multi-hop neighbor discovery
        self.multihop_neighbor_table = {}  # {neighbor_gui: {'hop_dist': int, 'next_hop': gui, 'distance': float}}
        
        # Node failure and recovery tracking
        self.is_failed = False
        self.failure_time = None
        self.role_before_failure = None
        self.children_before_failure = []

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
                self.set_timer('TIMER_EXPORT_CH_CSV', config.EXPORT_CH_CSV_INTERVAL)
                self.set_timer('TIMER_EXPORT_NEIGHBOR_CSV', config.EXPORT_NEIGHBOR_CSV_INTERVAL)

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
        self.neighbors_table[neighbor_entry['gui']] = neighbor_entry

        if neighbor_entry['gui'] not in self.child_networks_table.keys():
            if neighbor_entry['gui'] not in self.candidate_parents_table:
                self.candidate_parents_table.append(neighbor_entry['gui'])
        
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
        min_hop = 99999
        min_hop_gui = 99999
        for gui in self.candidate_parents_table:
            neighbor_info = self.neighbors_table.get(gui)
            if neighbor_info is None:
                continue
            hop_count = neighbor_info.get('hop_count', 99999)
            if hop_count < min_hop or (hop_count == min_hop and gui < min_hop_gui):
                min_hop = hop_count
                min_hop_gui = gui
        if min_hop_gui == 99999:
            return
        selected_entry = self.neighbors_table[min_hop_gui]
        selected_addr = selected_entry.get('source')
        if selected_addr is None:
            return
        self.send_join_request(selected_addr)
        self.set_timer('TIMER_JOIN_REQUEST', 5)


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
        self.send({'dest': dest, 'type': 'JOIN_REQUEST', 'gui': self.id})

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
        """Ensure every packet carries a creation timestamp."""
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

        super().send(pck)

    ###################
    def route_and_forward_package(self, pck):
        """Mesh-first routing with tree fallback."""
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

        route_trace = pck.setdefault('route_trace', [])
        if not route_trace or route_trace[-1] != self.id:
            route_trace.append(self.id)
        # Deliver to self if addressed directly
        if self.addr is not None and dest == self.addr:
            pck['next_hop'] = dest
            self._record_route(pck, 'LOCAL_SELF', dest)
            self.send(pck)
            return

        next_hop = None
        path_label = None

        if config.ENABLE_MESH_ROUTING:
            next_hop, path_label = self._find_direct_neighbor_hop(dest)
            if next_hop is None and config.ENABLE_MULTIHOP_DISCOVERY:
                next_hop, path_label = self._find_multihop_route(dest)

        if next_hop is None and self.role in (Roles.CLUSTER_HEAD, Roles.ROOT):
            # Check if destination is in members_table (simple list now)
            if dest in self.members_table:
                next_hop = dest
                path_label = 'CLUSTER_MEMBER'

        if next_hop is None and config.ENABLE_TREE_ROUTING:
            child_addr = self._find_child_route(dest)
            if child_addr is not None:
                next_hop = child_addr
                path_label = 'TREE_CHILD'

        if next_hop is None and config.ENABLE_TREE_ROUTING and self.ch_addr is not None and hasattr(dest, 'net_addr'):
            if dest.net_addr == self.ch_addr.net_addr:
                parent_addr = self._get_parent_next_hop()
                if parent_addr is not None:
                    next_hop = parent_addr
                    path_label = 'TREE_SAME_CLUSTER'

        if next_hop is None and config.ENABLE_TREE_ROUTING:
            parent_addr = self._get_parent_next_hop()
            if parent_addr is not None:
                next_hop = parent_addr
                path_label = 'TREE_PARENT'

        if next_hop is None:
            self.debug_log(config.ENABLE_ROUTING_DEBUG, f"[ROUTING] Node {self.id}: NO_ROUTE for type={pck.get('type')} dest={format_addr(dest)}")
            write_log(self, f"ROUTE_FAIL type={pck.get('type')} dest={format_addr(dest)}")
            return

        pck['next_hop'] = next_hop
        self._record_route(pck, path_label or 'UNKNOWN', next_hop)
        self.send(pck)

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
        self.route_and_forward_package({'dest': self.root_addr, 'type': 'NETWORK_REQUEST', 'source': self.addr})

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
        if self.addr is None:
            return
        eligible = [node for node in ALL_NODES
                    if hasattr(node, 'addr') and node.addr is not None and node.id != self.id]
        if not eligible:
            self.debug_log(config.ENABLE_ROUTING_DEBUG,
                           f"[DATA] Node {self.id}: No eligible destinations for SENSOR_DATA")
            return

        dest_node = random.choice(eligible)
        packet_id = next_packet_id()
        pck = {
            'packet_id': packet_id,
            'type': 'SENSOR_DATA',
            'source': self.addr,
            'source_gui': self.id,
            'dest': dest_node.addr,
            'dest_gui': dest_node.id,
            'sensor_value': random.uniform(0, 100),
            'route_trace': [self.id],
        }
        self.debug_log(config.ENABLE_ROUTING_DEBUG,
                       f"[DATA] Node {self.id}: Sending packet#{packet_id} to Node {dest_node.id}")
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
        # Ignore packets if node is failed
        if self.is_failed:
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
            if 'next_hop' in pck.keys() and pck['dest'] != self.addr and pck['dest'] != self.ch_addr:  # forwards message if destination is not itself
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
                
                # Count current children (excluding this child if already in pool)
                current_children = sum(1 for assigned_gui in self.node_addr_pool.values() 
                                     if assigned_gui is not None and assigned_gui != child_gui)
                
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
                        self.log(f"[CLUSTER_SIZE] ROOT Node {self.id}: Assigned cluster ID {cluster_id} to {pck['source']}")
                        self.send_network_reply(pck['source'], new_addr)
                    else:
                        self.log(f"[CLUSTER_SIZE] ROOT Node {self.id}: ERROR - No available cluster IDs! All {config.NUM_OF_CLUSTERS} clusters in use")
            if pck['type'] == 'JOIN_ACK':
                # Add member to list if within capacity
                member_addr = pck.get('source')
                if member_addr is not None and len(self.members_table) < config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER:
                    self.members_table.append(member_addr)
                    self.log(f"[MEMBER_TABLE] Node {self.id}: Added member {member_addr} (size={len(self.members_table)}/{config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER})")
                elif member_addr is not None:
                    self.log(f"[MEMBER_TABLE] Node {self.id}: REJECTED {member_addr} - members_table FULL")
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
            if pck['type'] == 'JOIN_REQUEST':  # it sends a network request to the root
                # Avoid duplicates in received_JR_guis
                if pck['gui'] not in self.received_JR_guis:
                    self.received_JR_guis.append(pck['gui'])
                # yield self.timeout(.5)
                self.send_network_request()
            if pck['type'] == 'NETWORK_REPLY':  # it becomes cluster head and send join reply to the candidates
                self.set_role(Roles.CLUSTER_HEAD)
                self.members_table = []
                try:
                    write_clusterhead_distances_csv("clusterhead_distances.csv")
                except Exception as e:
                    self.log(f"CH CSV export error: {e}")
                self.scene.nodecolor(self.id, 0, 0, 1)
                self.ch_addr = pck['addr']
                
                # Initialize address pool for new CLUSTER_HEAD
                self._init_address_pool()
                
                self.send_network_update()
                # yield self.timeout(.5)
                self.send_heart_beat()
                # Start neighbor sharing for CLUSTER_HEAD
                if config.ENABLE_MULTIHOP_DISCOVERY:
                    self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)
                
                # Process pending join requests (up to max allowed children)
                self.log(f"[CLUSTER_SIZE] Node {self.id}: Processing {len(self.received_JR_guis)} pending join requests")
                accepted_count = 0
                rejected_count = 0
                
                for gui in self.received_JR_guis:
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

        elif self.role == Roles.UNDISCOVERED:  # if the node is undiscovered
            if pck['type'] == 'HEART_BEAT':  # it kills probe timer, becomes unregistered and sets join request timer once received heart beat
                self.update_neighbor(pck)
                self.kill_timer('TIMER_PROBE')
                self.become_unregistered()

        if self.role == Roles.UNREGISTERED:  # if the node is unregistered
            if pck['type'] == 'HEART_BEAT':
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
                    self.send_heart_beat()
                    self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                    self.send_join_ack(pck['source'])
                    if self.ch_addr is not None: # it could be a cluster head which lost its parent
                        self.set_role(Roles.CLUSTER_HEAD)
                        self.send_network_update()
                    else:
                        self.set_role(Roles.REGISTERED)
                    # Start periodic neighbor sharing
                    if config.ENABLE_MULTIHOP_DISCOVERY:
                        self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)
                    self.set_timer('TIMER_SENSOR', max(1, config.DATA_PACKET_INTERVAL))
                    # # sensor implementation
                    # timer_duration =  self.id % 20
                    # if timer_duration == 0: timer_duration = 1
                    # self.set_timer('TIMER_SENSOR', timer_duration)

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
                    self.set_role(Roles.ROOT)
                    self.members_table = []
                    self.scene.nodecolor(self.id, 0, 0, 0)
                    self.addr = wsn.Addr(0, 254)  # ROOT uses net_addr=0
                    self.ch_addr = wsn.Addr(0, 254)
                    self.root_addr = self.addr
                    self.hop_count = 0
                    
                    # Initialize address pools for ROOT
                    self._init_address_pool()  # For direct children
                    self.cluster_addr_pool = {i: None for i in range(1, config.NUM_OF_CLUSTERS + 1)}  # For cluster IDs (start from 1, ROOT uses 0)
                    self.log(f"[CLUSTER_SIZE] ROOT Node {self.id}: Initialized pools - {config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER} child slots, {config.NUM_OF_CLUSTERS} cluster IDs (ROOT uses net_addr=0)")
                    
                    self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                    # Start neighbor sharing for ROOT
                    if config.ENABLE_MULTIHOP_DISCOVERY:
                        self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)
                else:  # otherwise it keeps trying to sending probe after a long time
                    self.c_probe = 0
                    self.set_timer('TIMER_PROBE', 30)

        elif name == 'TIMER_HEART_BEAT':  # it sends heart beat message once heart beat timer fired
            self.send_heart_beat()
            self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
            #print(self.id)
 
        elif name == 'TIMER_NEIGHBOR_SHARE':  # Periodic neighbor info sharing
            if config.ENABLE_MULTIHOP_DISCOVERY:
                self.share_neighbor_info()
                self.set_timer('TIMER_NEIGHBOR_SHARE', config.NEIGHBOR_SHARE_INTERVAL)

        elif name == 'TIMER_JOIN_REQUEST':  # if it has not received heart beat messages before, it sets timer again and wait heart beat messages once join request timer fired.
            if len(self.candidate_parents_table) == 0:
                self.become_unregistered()
            else:  # otherwise it chose one of them and sends join request
                self.select_and_join()

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

sim = wsn.Simulator(
    duration=config.SIM_DURATION,
    timescale=config.SIM_TIME_SCALE,
    visual=config.SIM_VISUALIZATION,
    terrain_size=config.SIM_TERRAIN_SIZE,
    title=config.SIM_TITLE)

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
