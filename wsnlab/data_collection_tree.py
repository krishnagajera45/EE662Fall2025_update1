import random
from enum import Enum
import sys
sys.path.insert(1, '.')
from source import wsnlab_vis as wsn
import math
from source import config
from collections import Counter

import csv  # <— add this near your other imports
from datetime import datetime
import os
random.seed(config.SEED if hasattr(config, "SEED") else 42)
# Track where each node is placed
NODE_POS = {}  # {node_id: (x, y)}

# Initialize log file
LOG_FILE = None
def init_log_file():
    """Initialize the log file with timestamp in filename."""
    global LOG_FILE
    timestamp = datetime.now().strftime("%d-%m-%y-%H%M")
    log_filename = f"wsn_log_{timestamp}.log"
    LOG_FILE = open(log_filename, "w")
    return log_filename

def write_log(node_id, message, sim_time=None):
    """Write a log entry to the log file.
    
    Args:
        node_id: Node ID (int or None) or SensorNode instance
        message: Log message string
        sim_time: Simulation time (optional, will try to get from node)
    """
    global LOG_FILE, sim
    if LOG_FILE is None:
        return
    try:
        # Get current simulation time
        if sim_time is None:
            # If node_id is a SensorNode instance, get time from it
            if hasattr(node_id, 'now'):
                sim_time = node_id.now
                actual_node_id = node_id.id
            # If node_id is an integer, try to get from ALL_NODES or sim
            elif isinstance(node_id, int):
                actual_node_id = node_id
                if node_id < len(ALL_NODES) and ALL_NODES[node_id] and hasattr(ALL_NODES[node_id], 'now'):
                    sim_time = ALL_NODES[node_id].now
                elif 'sim' in globals() and hasattr(sim, 'now'):
                    sim_time = sim.now
                else:
                    sim_time = 0.0
            else:
                actual_node_id = node_id
                if 'sim' in globals() and hasattr(sim, 'now'):
                    sim_time = sim.now
                else:
                    sim_time = 0.0
        else:
            # sim_time provided, extract node_id if node_id is a SensorNode
            if hasattr(node_id, 'id'):
                actual_node_id = node_id.id
            else:
                actual_node_id = node_id
        
        node_str = f"N{actual_node_id}" if actual_node_id is not None else "SYS"
        log_entry = f"[{sim_time:10.5f}] {node_str} {message}\n"
        LOG_FILE.write(log_entry)
        LOG_FILE.flush()  # Ensure immediate write
    except Exception:
        pass  # Silently fail to avoid disrupting simulation

def close_log_file():
    """Close the log file."""
    global LOG_FILE
    if LOG_FILE is not None:
        LOG_FILE.close()
        LOG_FILE = None

def log_node_state(node, from_node_id=None):
    """Log node state information.
    
    Args:
        node: SensorNode instance
        from_node_id: ID of node that triggered this update (for 'from' field)
    """
    try:
        role_name = _role_name(node.role)
        hop = node.hop_count if hasattr(node, 'hop_count') else 99999
        parent = node.parent_gui if hasattr(node, 'parent_gui') and node.parent_gui is not None else None
        
        # Count neighbors
        neighbor_count = len(node.local_neighbor_map) if hasattr(node, 'local_neighbor_map') else 0
        neighbor_list = sorted(node.local_neighbor_map.keys()) if hasattr(node, 'local_neighbor_map') else []
        neighbor_str = ','.join(map(str, neighbor_list)) if neighbor_list else ''
        
        # Separate 1-hop and 2-hop neighbors
        one_hop = []
        two_hop = []
        if hasattr(node, 'local_neighbor_map'):
            for n_id, n_data in node.local_neighbor_map.items():
                hop_dist = n_data.get('mesh_hop_distance', 1)
                if hop_dist == 1:
                    one_hop.append(n_id)
                elif hop_dist == 2:
                    two_hop.append(n_id)
        
        one_hop_str = ','.join(map(str, sorted(one_hop))) if one_hop else ''
        two_hop_str = ','.join(map(str, sorted(two_hop))) if two_hop else ''
        
        from_str = f"from={from_node_id}" if from_node_id is not None else "from=None"
        parent_str = f"parent={parent}" if parent is not None else "parent=None"
        
        msg = f"{from_str} role={role_name} hop={hop} {parent_str} neighs={neighbor_count}({neighbor_str}) 1hop={one_hop_str} 2hop={two_hop_str}"
        write_log(node, msg, node.now)
    except Exception:
        pass  # Silently fail

# --- tracking containers ---
ALL_NODES = []              # node objects
CLUSTER_HEADS = []
ROLE_COUNTS = Counter()     # live tally per Roles enum

# --- failure and recovery tracking ---
FAILED_NODES = set()  # Set of node IDs that are currently failed
ORPHAN_NODES = set()  # Set of node IDs that are currently orphaned
RECOVERY_EVENTS = []  # List of recovery events: [(node_id, failure_time, recovery_time, orphan_count)]
ORPHAN_EVENTS = []  # List of orphan events: [(node_id, time, reason)]
ROLE_CHANGE_EVENTS = []  # List of role change events: [(node_id, old_role, new_role, time)]

def _addr_str(a): return "" if a is None else str(a)
def _role_name(r): return r.name if hasattr(r, "name") else str(r)

# --- Recovery logging functions ---
def log_orphan_event(node_id, time, reason):
    """Log orphan event.
    
    Args:
        node_id (int): Node ID that became orphan
        time (float): Simulation time when orphaned
        reason (str): Reason for becoming orphan
    """
    ORPHAN_EVENTS.append({
        'node_id': node_id,
        'time': time,
        'reason': reason
    })
    write_log(node_id, f"ORPHAN_EVENT reason={reason}", time)

def log_join_network(node_id, time, join_type):
    """Log network join event.
    
    Args:
        node_id (int): Node ID that joined
        time (float): Simulation time when joined
        join_type (str): Type of join (initial_join, recovered_from_orphan, etc.)
    """
    write_log(node_id, f"JOIN_NETWORK type={join_type}", time)

def log_role_change(node_id, old_role, new_role, time):
    """Log role change event.
    
    Args:
        node_id (int): Node ID that changed role
        old_role (Roles): Previous role
        new_role (Roles): New role
        time (float): Simulation time when role changed
    """
    if old_role != new_role:
        ROLE_CHANGE_EVENTS.append({
            'node_id': node_id,
            'old_role': _role_name(old_role),
            'new_role': _role_name(new_role),
            'time': time
        })
        write_log(node_id, f"ROLE_CHANGE from={_role_name(old_role)} to={_role_name(new_role)}", time)


Roles = Enum('Roles', 'UNDISCOVERED UNREGISTERED ROOT REGISTERED CLUSTER_HEAD')
"""Enumeration of roles"""
def log_all_nodes_registered():
    """Log every node's status and role to topology.csv and check if all are registered."""
    filename = "topology.csv"

    # Create or overwrite the CSV file
    with open(filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Node ID", "Position", "Role"])

        unregistered_nodes = []

        for node in ALL_NODES:
            role = getattr(node, "role", "UNKNOWN")
            position = getattr(node, "pos", None)
            writer.writerow([node.id, position, role])

            if role not in {Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROOT}:
                unregistered_nodes.append(node.id)

    # Console output
    if not unregistered_nodes:
        print(f"✅ All {len(ALL_NODES)} nodes are registered. Logged to {filename}.")
        return True
    else:
        print(f"⚠️ Unregistered nodes: {unregistered_nodes}. Logged to {filename}.")
        return False
with open("registration_log.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["node_id", "start_time", "registered_time", "delta_time"])
def log_registration_time(node_id, start_time, registered_time, diff):
    with open("registration_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([node_id, start_time, registered_time, diff])

def calculate_and_log_average_packet_delay(path="packet_delays.csv", output_path="packet_delay_summary.csv"):
    """Calculate and log the average packet delivery delay.
    
    Args:
        path (str): Path to packet_delays.csv file
        output_path (str): Path to output summary file
    """
    try:
        delays = []
        delays_by_type = {}
        
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    delay = float(row['delay'])
                    ptype = row.get('packet_type', 'UNKNOWN')
                    delays.append(delay)
                    
                    # Group by packet type
                    if ptype not in delays_by_type:
                        delays_by_type[ptype] = []
                    delays_by_type[ptype].append(delay)
                except (ValueError, KeyError):
                    continue
        
        if not delays:
            print("⚠️ No packet delays found in packet_delays.csv")
            return
        
        avg_delay = sum(delays) / len(delays)
        min_delay = min(delays)
        max_delay = max(delays)
        total_packets = len(delays)
        
        # Write to summary CSV
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value"])
            writer.writerow(["total_packets_delivered", total_packets])
            writer.writerow(["average_delay", f"{avg_delay:.6f}"])
            writer.writerow(["min_delay", f"{min_delay:.6f}"])
            writer.writerow(["max_delay", f"{max_delay:.6f}"])
            
            # Add per-packet-type statistics
            writer.writerow([])  # Empty row
            writer.writerow(["packet_type", "count", "avg_delay", "min_delay", "max_delay"])
            for ptype, type_delays in sorted(delays_by_type.items()):
                type_avg = sum(type_delays) / len(type_delays)
                type_min = min(type_delays)
                type_max = max(type_delays)
                writer.writerow([ptype, len(type_delays), f"{type_avg:.6f}", f"{type_min:.6f}", f"{type_max:.6f}"])
        
        # Print to console
        print(f"\n{'='*60}")
        print(f"📦 PACKET DELIVERY DELAY STATISTICS")
        print(f"{'='*60}")
        print(f"Total packets delivered: {total_packets}")
        print(f"Average delay: {avg_delay:.6f} simulation time units")
        print(f"Minimum delay: {min_delay:.6f} simulation time units")
        print(f"Maximum delay: {max_delay:.6f} simulation time units")
        print(f"\nPer-packet-type statistics:")
        for ptype, type_delays in sorted(delays_by_type.items()):
            type_avg = sum(type_delays) / len(type_delays)
            type_min = min(type_delays)
            type_max = max(type_delays)
            print(f"  {ptype:20s}: count={len(type_delays):4d}, avg={type_avg:.6f}, min={type_min:.6f}, max={type_max:.6f}")
        print(f"{'='*60}\n")
        print(f"✅ Summary saved to {output_path}")
        
    except FileNotFoundError:
        print(f"⚠️ Could not find {path}. No packet delay statistics calculated.")
    except Exception as e:
        print(f"⚠️ Error calculating packet delay statistics: {e}")

def calculate_and_log_average_join_time(path="registration_log.csv", output_path="join_time_summary.csv"):
    """Calculate and log the average time to join the network.
    
    Args:
        path (str): Path to registration_log.csv file
        output_path (str): Path to output summary file
    """
    try:
        join_times = []
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    delta_time = float(row['delta_time'])
                    join_times.append(delta_time)
                except (ValueError, KeyError):
                    continue
        
        if not join_times:
            print("⚠️ No join times found in registration_log.csv")
            return
        
        avg_join_time = sum(join_times) / len(join_times)
        min_join_time = min(join_times)
        max_join_time = max(join_times)
        total_nodes = len(join_times)
        
        # Write to summary CSV
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value"])
            writer.writerow(["total_nodes_registered", total_nodes])
            writer.writerow(["average_join_time", f"{avg_join_time:.6f}"])
            writer.writerow(["min_join_time", f"{min_join_time:.6f}"])
            writer.writerow(["max_join_time", f"{max_join_time:.6f}"])
        
        # Print to console
        print(f"\n{'='*60}")
        print(f"📊 JOIN TIME STATISTICS")
        print(f"{'='*60}")
        print(f"Total nodes registered: {total_nodes}")
        print(f"Average join time: {avg_join_time:.6f} simulation time units")
        print(f"Minimum join time: {min_join_time:.6f} simulation time units")
        print(f"Maximum join time: {max_join_time:.6f} simulation time units")
        print(f"{'='*60}\n")
        print(f"✅ Summary saved to {output_path}")
        
    except FileNotFoundError:
        print(f"⚠️ Could not find {path}. No join time statistics calculated.")
    except Exception as e:
        print(f"⚠️ Error calculating join time statistics: {e}")
def check_all_nodes_registered():
    """Log every node's status and role to topology.csv and check if all are registered."""

    unregistered_nodes = []

    for node in ALL_NODES:
        role = getattr(node, "role", "UNKNOWN")
        position = getattr(node, "pos", None)

        if role not in {Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROOT}:
            unregistered_nodes.append(node.id)

    # Console output
    if not unregistered_nodes:
        print(f"✅ All {len(ALL_NODES)} nodes are registered. {sim.now}")
        return True
    else:
        return False
###########################################################
class SensorNode(wsn.Node):
    """SensorNode class is inherited from Node class in wsnlab.py.
    It will run data collection tree construction algorithms.

    Attributes:
        role (Roles): role of node
        is_root_eligible (bool): keeps eligibility to be root
        c_probe (int): probe message counter
        th_probe (int): probe message threshold
        local_neighbor_map (Dict): maintains information about discovered neighboring nodes
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
        self.ch_addr = None #clusterhead address
        self.parent_gui = None
        self.root_addr = None
        self.wake_up_time = None
        self.set_role(Roles.UNDISCOVERED)
        self.is_root_eligible = True if self.id == ROOT_ID else False
        self.c_probe = 0  # c means counter and probe is the name of counter
        self.th_probe = 10  # th means threshold and probe is the name of threshold
        self.hop_count = 99999
        self.local_neighbor_map = {}  # maintains information about discovered neighboring nodes
        self.candidate_parents_table = []
        self.child_networks_table = {}
        self.members_table = []
        self.net_req_flag = None
        self.received_JR_guis = []  # keeps received Join Request global unique ids
        # Address pool management for cluster size control
        self.node_available_dict = {}  # Pool of child node IDs: {node_id: gui or None}
        self.net_id_available_dict = {}  # Pool of cluster network IDs (ROOT only): {net_id: source or None}
        # Transmission power management
        self.tx_power = config.NODE_DEFAULT_TX_POWER  # Transmission power level (dBm), will be updated when joining cluster
        self.tx_current = config.TX_CURRENTS[config.NODE_DEFAULT_TX_POWER]  # Current consumption for TX (mA)
        # Failure and recovery tracking
        self.is_failed = False  # Whether this node is currently failed
        self.failure_time = None  # Time when node failed
        self.recovery_time = None  # Time when node recovered
        self.was_orphan = False  # Whether node was orphaned during failure
        self.last_heartbeat_time = {}  # Track last heartbeat time from each neighbor
        ALL_NODES.append(self)
    ###################
    def run(self):
        """Setting the arrival timer to wake up after firing.

        Args:

        Returns:

        """
        self.set_timer('TIMER_ARRIVAL', self.arrival)

    ###################
    def register(self):
        # Called when node successfully registers
        self.registered_time = self.now
        diff = self.registered_time - self.wake_up_time
        print(f"Node {self.id} registered at {self.registered_time}, Δt = {diff}")
        log_registration_time(self.id, self.wake_up_time, self.registered_time, diff)
        # Log JOIN_TIME
        write_log(self.id, f"JOIN_TIME started={self.wake_up_time:.3f} completed={self.registered_time:.3f} delay={diff:.3f}", self.now)

    def assign_tx_power(self, power_level=None):
        """Assign transmission power level to node.
        
        Args:
            power_level (str): Power level in dBm (e.g., "0 dBm"). If None, uses smart selection.
        """
        if power_level is None:
            # Smart power selection: choose minimum power needed to reach parent
            if self.parent_gui is not None:
                # Find parent details in candidate_parents_table
                parent = next(
                    (d for d in self.candidate_parents_table if isinstance(d, dict) and d.get('gui') == self.parent_gui),
                    None
                )
                if parent and 'distance' in parent:
                    parent_distance = parent['distance']
                    self.log(f"[DEBUG TX_POWER] Node {self.id}: Smart power selection, parent distance={parent_distance:.2f}m")
                    
                    # Calculate distance differences for each power level
                    dist_diff = []
                    for power_lvl in config.TX_POWER_LEVELS:
                        range_val = config.NODE_TX_RANGES[power_lvl]
                        diff = parent_distance - range_val
                        dist_diff.append(diff)
                    
                    # Find the index of the smallest *negative* distance difference (power that can reach)
                    negative_diffs = [(i, d) for i, d in enumerate(dist_diff) if d < 0]
                    
                    if negative_diffs:
                        # Choose the power level with the smallest negative diff (minimum power that reaches)
                        dist_diff_idx, _ = max(negative_diffs, key=lambda x: x[1])
                    else:
                        # Fallback: pick the smallest absolute difference
                        dist_diff_idx = min(range(len(dist_diff)), key=lambda i: abs(dist_diff[i]))
                    
                    power_level = config.TX_POWER_LEVELS[dist_diff_idx]
                    self.log(f"[DEBUG TX_POWER] Node {self.id}: Selected {power_level} (range={config.NODE_TX_RANGES[power_level]}m) to reach parent at {parent_distance:.2f}m")
                else:
                    # No parent info available, use default
                    power_level = config.NODE_DEFAULT_TX_POWER
                    self.log(f"[DEBUG TX_POWER] Node {self.id}: No parent info, using default {power_level}")
            else:
                # No parent, use default
                power_level = config.NODE_DEFAULT_TX_POWER
                self.log(f"[DEBUG TX_POWER] Node {self.id}: No parent, using default {power_level}")
        
        # Assign power level
        self.tx_power = power_level
        self.tx_current = config.TX_CURRENTS[power_level]
        self.tx_range = config.NODE_TX_RANGES[power_level] * config.SCALE
        
        # Update base class attributes
        if hasattr(self, 'power'):
            pass  # Already initialized in base class
        
        self.log(f"[DEBUG TX_POWER] Node {self.id}: Assigned tx_power={self.tx_power}, tx_current={self.tx_current}mA, tx_range={self.tx_range:.2f}m")
        # Get role name safely (role may not be set during initialization)
        role_name = _role_name(getattr(self, 'role', Roles.UNDISCOVERED))
        write_log(self.id, f"TX_POWER_UPDATE role={role_name} power={self.tx_power} current={self.tx_current} range={self.tx_range:.2f}", self.now)

    def set_role(self, new_role, *, recolor=True):
        """Central place to switch roles, keep tallies, and (optionally) recolor."""
        old_role = getattr(self, "role", None)
        if old_role is not None and old_role != new_role:
            ROLE_COUNTS[old_role] -= 1
            if ROLE_COUNTS[old_role] <= 0:
                ROLE_COUNTS.pop(old_role, None)
            # Log role change
            log_role_change(self.id, old_role, new_role, self.now)
        ROLE_COUNTS[new_role] += 1
        self.role = new_role

        if recolor:
            if new_role == Roles.UNDISCOVERED:
                self.scene.nodecolor(self.id, 1, 1, 1)
            elif new_role == Roles.UNREGISTERED:
                self.scene.nodecolor(self.id, 1, 1, 0)
            elif new_role == Roles.REGISTERED:
                self.scene.nodecolor(self.id, 0, 1, 0)
            elif new_role == Roles.CLUSTER_HEAD:
                self.scene.nodecolor(self.id, 0, 0, 1)
                # Assign power: smart selection if enabled, else keep current (from NETWORK_REPLY)
                if config.ALLOW_TX_POWER_CHOICE and self.tx_power == config.NODE_DEFAULT_TX_POWER:
                    self.assign_tx_power()  # Smart selection
                self.draw_tx_range()
            elif new_role == Roles.ROOT:
                self.scene.nodecolor(self.id, 0, 0, 0)
                self.set_timer('TIMER_EXPORT_CH_CSV', config.EXPORT_CH_CSV_INTERVAL)
                self.set_timer('TIMER_EXPORT_NEIGHBOR_CSV', config.EXPORT_NEIGHBOR_CSV_INTERVAL)




    
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
        self.local_neighbor_map = {}
        self.candidate_parents_table = []
        self.child_networks_table = {}
        self.members_table = []
        self.received_JR_guis = []  # keeps received Join Request global unique ids
        self.send_probe()
        self.set_timer('TIMER_JOIN_REQUEST', 20)

    ###################
    def check_neighbors(self):
        """Checks neighbors if they are still alive or not. If not, updates necessary tables.
        Detects parent failure and triggers recovery.
        
        Args:
        
        Returns:
        
        """
        if self.is_failed:
            return  # Don't check neighbors if this node is failed
        
        timeout_threshold = config.HEART_BEAT_TIME_INTERVAL * config.NEIGHBOR_TIMEOUT_MULTIPLIER
        childs_updated = False
        parent_dead = False
        will_be_removed = []
        
        for gui, pck in self.local_neighbor_map.items():
            last_hb_time = self.last_heartbeat_time.get(gui, pck.get('arrival_time', 0))
            if self.now - last_hb_time > timeout_threshold:
                # Neighbor is dead or failed
                will_be_removed.append(gui)
                if gui == self.parent_gui:
                    parent_dead = True
                    self.log(f"[RECOVERY] Node {self.id}: Parent {gui} appears dead (no heartbeat for {self.now - last_hb_time:.2f}s)")
                if gui in self.child_networks_table.keys():
                    del self.child_networks_table[gui]
                    childs_updated = True
                # Remove from candidate_parents_table
                self.candidate_parents_table = [c for c in self.candidate_parents_table 
                                                if (isinstance(c, dict) and c.get('gui') != gui) or c != gui]
        
        # Remove dead neighbors
        for gui in will_be_removed:
            if gui in self.local_neighbor_map:
                del self.local_neighbor_map[gui]
            if gui in self.last_heartbeat_time:
                del self.last_heartbeat_time[gui]
        
        # Handle parent failure
        if self.role != Roles.UNREGISTERED and self.role != Roles.UNDISCOVERED:
            if parent_dead:
                self.log(f"[RECOVERY] Node {self.id}: Starting recovery due to parent failure")
                log_orphan_event(self.id, self.now, f"parent_timeout:{self.parent_gui}")
                ORPHAN_NODES.add(self.id)
                self.was_orphan = True
                self.repair()
            elif childs_updated:
                if self.role != Roles.ROOT:
                    self.send_network_update()

    ###################
    def repair(self):
        """Executes chosen repairing instructions.
        
        Args:
        
        Returns:
        
        """
        if self.role == Roles.REGISTERED:
            self.log(f"[RECOVERY] Node {self.id}: Repairing as REGISTERED node")
            self.become_unregistered()
        elif self.role == Roles.CLUSTER_HEAD:
            if config.REPAIRING_METHOD == 'ALL_ORPHAN':
                self.log(f"[RECOVERY] Node {self.id}: Repairing with ALL_ORPHAN method")
                self.repair_all_orphan()
            elif config.REPAIRING_METHOD == 'FIND_ANOTHER_PARENT':
                self.log(f"[RECOVERY] Node {self.id}: Repairing with FIND_ANOTHER_PARENT method")
                self.repair_find_another_parent()
    
    ###################
    def repair_all_orphan(self):
        """Becomes unregistered and sends I am orphan message.
        
        Args:
        
        Returns:
        
        """
        self.send_i_am_orphan()
        self.become_unregistered()
    
    ###################
    def repair_find_another_parent(self):
        """If it has potential parent in its table, tries to connect any of them. Otherwise becomes unregistered.
        
        Args:
        
        Returns:
        
        """
        # Remove dead parent from candidate_parents_table
        if self.parent_gui is not None:
            self.candidate_parents_table = [c for c in self.candidate_parents_table 
                                            if (isinstance(c, dict) and c.get('gui') != self.parent_gui) or c != self.parent_gui]
            if self.parent_gui in self.local_neighbor_map:
                del self.local_neighbor_map[self.parent_gui]
        
        if len(self.candidate_parents_table) > 0:
            self.kill_all_timers()
            self.erase_parent()
            self.set_role(Roles.UNREGISTERED)
            self.select_and_join()
        else:
            self.log(f"[RECOVERY] Node {self.id}: No alternative parent found, becoming unregistered")
            self.become_unregistered()
    
    ###################
    def send_i_am_orphan(self):
        """Sends i am orphan message to inform its neighbors.
        
        Args:
        
        Returns:
        
        """
        pck = {'dest': wsn.BROADCAST_ADDR,
               'type': 'I_AM_ORPHAN',
               'source': self.ch_addr if self.ch_addr is not None else self.addr,
               'gui': self.id,
               'created_at': self.now}
        write_log(self.id, f"PKT_CREATE type=I_AM_ORPHAN created_at={self.now:.3f}", self.now)
        self.send(pck)

    ###################
    def fail_node(self):
        """Fail this node - put it to sleep and mark as failed.
        
        Args:
        
        Returns:
        
        """
        if self.is_failed:
            return  # Already failed
        
        self.is_failed = True
        self.failure_time = self.now
        FAILED_NODES.add(self.id)
        self.sleep()
        self.kill_all_timers()
        self.scene.nodecolor(self.id, 1, 1, 1)  # White color for failed node
        self.log(f"[FAILURE] Node {self.id}: FAILED at time {self.now:.3f}")
        write_log(self.id, f"NODE_FAILURE time={self.now:.3f}", self.now)
        
        # Check if any nodes will become orphan due to this failure
        self.check_orphan_children()
    
    ###################
    def recover_node(self):
        """Recover this node - wake it up and restart registration process.
        
        Args:
        
        Returns:
        
        """
        if not self.is_failed:
            return  # Not failed
        
        self.is_failed = False
        self.recovery_time = self.now
        recovery_duration = self.recovery_time - self.failure_time
        FAILED_NODES.discard(self.id)
        
        # Count orphan nodes at recovery time
        orphan_count = len(ORPHAN_NODES)
        
        self.wake_up()
        self.scene.nodecolor(self.id, 1, 0, 0)  # Red color for recovering node
        self.log(f"[RECOVERY] Node {self.id}: RECOVERED at time {self.now:.3f} (was failed for {recovery_duration:.3f}s)")
        write_log(self.id, f"NODE_RECOVERY time={self.now:.3f} failure_duration={recovery_duration:.3f} orphan_count={orphan_count}", self.now)
        
        # Log recovery event
        RECOVERY_EVENTS.append({
            'node_id': self.id,
            'failure_time': self.failure_time,
            'recovery_time': self.recovery_time,
            'recovery_duration': recovery_duration,
            'orphan_count': orphan_count
        })
        
        # Restart registration process
        if self.role == Roles.ROOT:
            # ROOT should not fail, but if it does, restart as ROOT
            self.set_role(Roles.ROOT)
            self.set_timer('TIMER_HEART_BEAT', config.HEART_BEAT_TIME_INTERVAL)
        else:
            # Become unregistered and try to rejoin
            self.become_unregistered()
    
    ###################
    def check_orphan_children(self):
        """Check if any child nodes will become orphan due to this node's failure.
        
        Args:
        
        Returns:
        
        """
        # This will be detected by children when they check_neighbors() and find parent timeout
        pass

    ###################
    def update_neighbor(self, pck):
        pck = pck.copy()
        pck['arrival_time'] = self.now
        # compute Euclidean distance between self and neighbor
        if pck['gui'] in NODE_POS and self.id in NODE_POS:
            x1, y1 = NODE_POS[self.id]
            x2, y2 = NODE_POS[pck['gui']]
            pck['distance'] = math.hypot(x1 - x2, y1 - y2)
        pck['mesh_hop_distance'] = 1
        self.local_neighbor_map[pck['gui']] = pck
        # Update last heartbeat time for failure detection
        self.last_heartbeat_time[pck['gui']] = self.now

        if pck.get('addr') is not None:
            if pck['gui'] not in self.child_networks_table.keys() or pck['addr'] not in self.members_table:
                # Store full packet info in candidate_parents_table for distance-based power selection
                # Check if this GUI is already in candidate_parents_table
                gui_exists = False
                for candidate in self.candidate_parents_table:
                    if isinstance(candidate, dict):
                        if candidate.get('gui') == pck['gui']:
                            gui_exists = True
                            break
                    elif candidate == pck['gui']:
                        gui_exists = True
                        break
                
                if not gui_exists:
                    self.candidate_parents_table.append(pck.copy())
        
        # Log node state after neighbor update
        log_node_state(self, from_node_id=pck.get('gui'))

    ###################
    def select_and_join(self):
        min_hop = 99999
        min_hop_gui = 99999
        for candidate in self.candidate_parents_table:
            # Handle both dict (new format) and int (old format) for backward compatibility
            if isinstance(candidate, dict):
                gui = candidate.get('gui')
                if gui is None:
                    continue
            else:
                gui = candidate
            
            if gui in self.local_neighbor_map:
                hop_count = self.local_neighbor_map[gui].get('hop_count', 99999)
                if hop_count < min_hop or (hop_count == min_hop and gui < min_hop_gui):
                    min_hop = hop_count
                min_hop_gui = gui
        
        if min_hop_gui != 99999:
            # Get address from local_neighbor_map or candidate_parents_table
            selected_addr = None
            if min_hop_gui in self.local_neighbor_map:
                selected_addr = self.local_neighbor_map[min_hop_gui].get('addr') or self.local_neighbor_map[min_hop_gui].get('source')
            else:
                # Try to get from candidate_parents_table
                for candidate in self.candidate_parents_table:
                    if isinstance(candidate, dict) and candidate.get('gui') == min_hop_gui:
                        selected_addr = candidate.get('addr') or candidate.get('source')
                        break
                    elif candidate == min_hop_gui:
                        # Old format, need to get from local_neighbor_map
                        if min_hop_gui in self.local_neighbor_map:
                            selected_addr = self.local_neighbor_map[min_hop_gui].get('addr') or self.local_neighbor_map[min_hop_gui].get('source')
                        break
            
            if selected_addr is not None:
                self.send_join_request(selected_addr)
                self.set_timer('TIMER_JOIN_REQUEST', config.JOIN_REQUEST_TIME_INTERVAL)


    ###################
    def send(self, pck):
        """Override send to add TX_SEND logging."""
        # Log TX_SEND before sending
        next_hop = pck.get('next_hop')
        if next_hop is not None:
            next_hop_str = str(next_hop)
        else:
            dest = pck.get('dest')
            next_hop_str = str(dest) if dest is not None else "BROADCAST"
        ptype = pck.get('type', 'UNKNOWN')
        write_log(self.id, f"TX_SEND type={ptype} next={next_hop_str}", self.now)
        self.log(f"[DEBUG] SensorNode.send() called: type={ptype}, from={self.id}, next_hop={next_hop_str}")
        super().send(pck)

    ###################
    def send_probe(self):
        """Sending probe message to be discovered and registered.

        Args:

        Returns:

        """
        pck = {'dest': wsn.BROADCAST_ADDR, 'type': 'PROBE', 'created_at': self.now}
        write_log(self.id, f"PKT_CREATE type=PROBE created_at={self.now:.3f}", self.now)
        self.send(pck)

    ###################
    def send_heart_beat(self):
        """Sending heart beat message

        Args:

        Returns:

        """
        pck = {'dest': wsn.BROADCAST_ADDR,
                   'type': 'HEART_BEAT',
                   'source': self.ch_addr if self.ch_addr is not None else self.addr,
                   'gui': self.id,
                   'role': self.role,
                   'addr': self.addr,
                   'ch_addr': self.ch_addr,
                   'hop_count': self.hop_count,
                   'created_at': self.now}
        write_log(self.id, f"PKT_CREATE type=HEART_BEAT created_at={self.now:.3f}", self.now)
        self.send(pck)

    ###################
    def send_join_request(self, dest):
        """Sending join request message to given destination address to join destination network

        Args:
            dest (Addr): Address of destination node
        Returns:

        """
        pck = {'dest': dest, 'type': 'JOIN_REQUEST', 'gui': self.id, 'created_at': self.now}
        write_log(self.id, f"PKT_CREATE type=JOIN_REQUEST created_at={self.now:.3f}", self.now)
        self.send(pck)

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
        # Include cluster tx_power in JOIN_REPLY (always include, even in UNIFORM mode)
        pck = {'dest': wsn.BROADCAST_ADDR, 'type': 'JOIN_REPLY', 'source': self.ch_addr,
                   'gui': self.id, 'dest_gui': gui, 'addr': addr, 'root_addr': self.root_addr,
                   'hop_count': self.hop_count+1, 'tx_power': self.tx_power, 'created_at': self.now}
        self.log(f"[DEBUG TX_POWER] CLUSTER_HEAD Node {self.id}: Sending JOIN_REPLY to node {gui} with tx_power={self.tx_power}")
        write_log(self.id, f"PKT_CREATE type=JOIN_REPLY created_at={self.now:.3f}", self.now)
        self.send(pck)

    ###################
    def send_join_ack(self, dest):
        """Sending join acknowledgement message to given destination address.

        Args:
            dest (Addr): Address of destination node
        Returns:

        """
        pck = {'dest': dest, 'type': 'JOIN_ACK', 'source': self.addr,
                   'gui': self.id, 'created_at': self.now}
        write_log(self.id, f"PKT_CREATE type=JOIN_ACK created_at={self.now:.3f}", self.now)
        self.send(pck)

    ###################
    def route_and_forward_package(self, pck):
        """Routing and forwarding given package
        Implements mesh routing first (using neighbor_table), falls back to tree routing.

        Args:
            pck (Dict): package to route and forward, should contain dest, source, and type.
        """
        # Timestamp packet creation if not already timestamped
        if 'created_at' not in pck:
            pck['created_at'] = self.now
        
        path_str = "UNKNOWN"  # default
        dest = pck.get('dest')
        
        # Step 1: Check if destination is myself or my cluster head
        if dest == self.addr or (self.ch_addr is not None and dest == self.ch_addr):
            # Destination is me - deliver directly
            pck["next_hop"] = dest
            path_str = "LOCAL"
            next_hop_str = str(pck.get('next_hop', 'UNKNOWN'))
            log_packet_route(pck, self, next_hop_str, path_str)
            self.send(pck)
            return

        # Step 2: Mesh routing - check local_neighbor_map first
        neighbor_match = None
        for neighbor_entry in self.local_neighbor_map.values():
            neighbor_addr = neighbor_entry.get('addr')
            neighbor_ch_addr = neighbor_entry.get('ch_addr')
            if (neighbor_addr is not None and neighbor_addr == dest) or \
               (neighbor_ch_addr is not None and neighbor_ch_addr == dest):
                neighbor_match = neighbor_entry
                break

        if neighbor_match:
            # Found in local_neighbor_map - use mesh routing
            hop_distance = neighbor_match.get('mesh_hop_distance', 1)
            if hop_distance == 1:
                # Direct neighbor - send directly
                pck['next_hop'] = dest
                path_str = "DIRECT"
            else:
                # Multi-hop neighbor - use next_hop from local_neighbor_map
                pck['next_hop'] = neighbor_match.get('next_hop', dest)
                path_str = "MESH"
            next_hop_str = str(pck.get('next_hop', 'UNKNOWN'))
            log_packet_route(pck, self, next_hop_str, path_str)
            self.send(pck)
            return

        # Step 3: Check if destination is in members_table (same cluster)
        if dest in self.members_table:
            # Member of my cluster - send directly
            pck['next_hop'] = dest
            path_str = "CLUSTER_DIRECT"
            next_hop_str = str(pck.get('next_hop', 'UNKNOWN'))
            log_packet_route(pck, self, next_hop_str, path_str)
            self.send(pck)
            return

        # Step 4: Tree routing - check if destination is in child networks
        if self.ch_addr is not None and dest is not None and hasattr(dest, 'net_addr'):
            # Check if destination is in same network
            if dest.net_addr == self.ch_addr.net_addr:
                pck['next_hop'] = dest
                path_str = "TREE_SAME_NET"
                next_hop_str = str(pck.get('next_hop', 'UNKNOWN'))
                log_packet_route(pck, self, next_hop_str, path_str)
                self.send(pck)
                return
            
            # Check if destination is in child networks
            for child_gui, child_networks in self.child_networks_table.items():
                if dest.net_addr in child_networks:
                    # Route to child cluster head
                    if child_gui in self.local_neighbor_map:
                        pck['next_hop'] = self.local_neighbor_map[child_gui].get('addr')
                        path_str = "TREE_CHILD"
                        next_hop_str = str(pck.get('next_hop', 'UNKNOWN'))
                        log_packet_route(pck, self, next_hop_str, path_str)
                        if pck.get('next_hop') is not None:
                            self.send(pck)
                        return

        # Step 5: Default tree routing - send to parent (up the tree)
        if self.role != Roles.ROOT:
            if self.parent_gui and self.parent_gui in self.local_neighbor_map:
                parent_entry = self.local_neighbor_map[self.parent_gui]
                parent_ch_addr = parent_entry.get('ch_addr')
                if parent_ch_addr is not None:
                    pck['next_hop'] = parent_ch_addr
                    path_str = "TREE_PARENT"
                else:
                    # No parent CH address - cannot route
                    path_str = "NO_ROUTE"
                    pck['next_hop'] = None
            else:
                # No parent - cannot route
                path_str = "NO_ROUTE"
                pck['next_hop'] = None
        else:
            # Root node - cannot route further up
            path_str = "NO_ROUTE"
            pck['next_hop'] = None

        # Log and send the packet
        next_hop_str = str(pck.get('next_hop', 'UNKNOWN'))
        log_packet_route(pck, self, next_hop_str, path_str)
        if pck.get('next_hop') is not None:
            self.send(pck)

    ###################
    def send_network_request(self):
        """Sending network request message to root address to be cluster head

        Args:

        Returns:

        """
        pck = {'dest': self.root_addr, 'type': 'NETWORK_REQUEST', 'source': self.addr, 'created_at': self.now}
        write_log(self.id, f"PKT_CREATE type=NETWORK_REQUEST created_at={self.now:.3f}", self.now)
        self.route_and_forward_package(pck)

    ###################
    def send_network_reply(self, dest, addr):
        """Sending network reply message to dest address to be cluster head with a new adress

        Args:
            dest (Addr): destination address
            addr (Addr): cluster head address of new network

        Returns:

        """
        # Assign cluster tx_power based on mode
        if config.TX_POWER_MODE == 'PER_CLUSTER':
            # Assign random power level from available levels for this cluster
            tx_power = random.choice(config.TX_POWER_LEVELS)
            self.log(f"[DEBUG TX_POWER] ROOT Node {self.id}: Assigned cluster tx_power={tx_power} to cluster {addr} (range={config.NODE_TX_RANGES[tx_power]}m)")
            write_log(self.id, f"TX_POWER_ASSIGN cluster={addr} power={tx_power} range={config.NODE_TX_RANGES[tx_power]}", self.now)
        else:
            # UNIFORM mode - use default power
            tx_power = config.NODE_DEFAULT_TX_POWER
            self.log(f"[DEBUG TX_POWER] ROOT Node {self.id}: UNIFORM mode - using {tx_power} (range={config.NODE_TX_RANGES[tx_power]}m) for cluster {addr}")
        
        pck = {'dest': dest, 'type': 'NETWORK_REPLY', 'source': self.addr, 'addr': addr, 'tx_power': tx_power, 'created_at': self.now}
        write_log(self.id, f"PKT_CREATE type=NETWORK_REPLY created_at={self.now:.3f}", self.now)
        self.route_and_forward_package(pck)

    ###################
    def send_network_update(self):
        """Sending network update message to parent using routing

        Args:

        Returns:

        """
        child_networks = [self.ch_addr.net_addr]
        for networks in self.child_networks_table.values():
            child_networks.extend(networks)

        # Use routing to send to parent
        if self.parent_gui and self.parent_gui in self.local_neighbor_map:
            parent_entry = self.local_neighbor_map[self.parent_gui]
            parent_ch_addr = parent_entry.get('ch_addr')
            if parent_ch_addr is not None:
                pck = {
                    'dest': parent_ch_addr, 
                    'type': 'NETWORK_UPDATE', 
                    'source': self.addr,
                    'gui': self.id, 
                    'child_networks': child_networks,
                    'created_at': self.now
                }
                write_log(self.id, f"PKT_CREATE type=NETWORK_UPDATE created_at={self.now:.3f}", self.now)
                self.route_and_forward_package(pck)
    ###################
    def send_sensor_data(self):
        """Sending network update message to parent

        Args:

        Returns:

        """
        #print(self.local_neighbor_map)
        #print(len(self.local_neighbor_map))
        #choose random node from local neighbor map
        #    self.route_and_forward_package({'dest': self.root_addr, 'type': 'SENSOR', 'source': self.addr, 'sensor_value': random.uniform(10,50)})
        if self.local_neighbor_map:
            rand_key = random.choice(list(self.local_neighbor_map.keys()))
            #self.send({'dest': self.local_neighbor_map[rand_key]['addr'], 'type': 'SENSOR_DATA', 'source': self.addr,
            #       'gui': self.id, 'sensor_value': random.uniform(0,100)})
            self.route_and_forward_package({'dest': self.local_neighbor_map[rand_key]['addr'], 'type': 'SENSOR_DATA', 'source': self.addr,
               'gui': self.id, 'sensor_value': random.uniform(0,100)})
    ###################
    def broadcast_neighbor_info(self):
        """Broadcasts neighbor information to enable multi-hop mesh routing discovery.

        Args:

        Returns:

        """
        # For N-hop mesh routing, share neighbors that are exactly N hops away
        discovered_mesh_neighbors = {}
        for neighbor_id, neighbor_data in self.local_neighbor_map.items():
            if neighbor_data['mesh_hop_distance'] == config.MAX_MESH_DISCOVERY_HOPS:
                discovered_mesh_neighbors[neighbor_id] = neighbor_data
        # Send collected neighbor information to all immediate (1-hop) neighbors
        for neighbor_entry in self.local_neighbor_map.values():
            if neighbor_entry['mesh_hop_distance'] == config.MAX_MESH_DISCOVERY_HOPS:
                pck = {'dest': neighbor_entry['source'], 'type': 'NEIGHBOR_INFO_BROADCAST', 'source': self.addr,
                        'gui': self.id, 'neighbors': discovered_mesh_neighbors, 'created_at': self.now}
                write_log(self.id, f"PKT_CREATE type=NEIGHBOR_INFO_BROADCAST created_at={self.now:.3f}", self.now)
                self.send(pck)

    ###################
    def on_receive(self, pck):
        """Executes when a package received.

        Args:
            pck (Dict): received package
        Returns:

        """
        # Check if packet reached final destination and log delay
        dest = pck.get('dest')
        next_hop = pck.get('next_hop')
        is_final_destination = False
        
        # Check for JOIN_REPLY packets (use dest_gui instead of dest)
        if pck.get('type') == 'JOIN_REPLY' and pck.get('dest_gui') == self.id:
            is_final_destination = True
        # Check if destination is this node or its cluster head
        elif dest is not None:
            # Don't log broadcast packets as final destination
            if hasattr(dest, 'is_equal') and dest.is_equal(wsn.BROADCAST_ADDR):
                is_final_destination = False
            # Check if destination matches this node or its cluster head
            elif (self.addr is not None and dest == self.addr) or \
                 (self.ch_addr is not None and dest == self.ch_addr):
                # If next_hop is set, check if it matches final destination (not being forwarded)
                if next_hop is None:
                    is_final_destination = True
                elif (self.addr is not None and next_hop == self.addr) or \
                     (self.ch_addr is not None and next_hop == self.ch_addr):
                    is_final_destination = True
        
        # Log delay if packet reached final destination
        if is_final_destination and 'created_at' in pck:
                    log_packet_delivery(pck, self)

        if self.role == Roles.ROOT or self.role == Roles.CLUSTER_HEAD:  # if the node is root or cluster head
            if 'next_hop' in pck.keys() and pck['dest'] != self.addr and (self.ch_addr is None or pck['dest'] != self.ch_addr):  # forwards message if destination is not itself
                self.route_and_forward_package(pck)
                return
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'PROBE':  # it waits and sends heart beat message once received probe message
                # yield self.timeout(.5)
                self.send_heart_beat()
            if pck['type'] == 'JOIN_REQUEST':  # it waits and sends join reply message once received join request
                # DEBUG: Check address pool before assignment
                self.log(f"[DEBUG CLUSTER_SIZE] CLUSTER_HEAD Node {self.id}: Received JOIN_REQUEST from node {pck['gui']}")
                self.log(f"[DEBUG CLUSTER_SIZE] CLUSTER_HEAD Node {self.id}: Current pool status - total={len(self.node_available_dict)}, used={sum(1 for v in self.node_available_dict.values() if v is not None)}, available={sum(1 for v in self.node_available_dict.values() if v is None)}")
                
                # Search for available address in pool
                avail_node_id = None
                for node_id, avail in self.node_available_dict.items():
                    if avail is None or avail == pck['gui']:
                        avail_node_id = node_id
                        break
                
                if avail_node_id is not None and self.ch_addr is not None:
                    # Address available - assign it
                    self.node_available_dict[avail_node_id] = pck['gui']  # Mark as used
                    assigned_addr = wsn.Addr(self.ch_addr.net_addr, avail_node_id)
                    self.log(f"[DEBUG CLUSTER_SIZE] CLUSTER_HEAD Node {self.id}: ASSIGNED address {assigned_addr} to node {pck['gui']} (node_id={avail_node_id})")
                    self.log(f"[DEBUG CLUSTER_SIZE] CLUSTER_HEAD Node {self.id}: Pool after assignment - used={sum(1 for v in self.node_available_dict.values() if v is not None)}/{len(self.node_available_dict)}")
                    self.send_join_reply(pck['gui'], assigned_addr)
                else:
                    # Cluster is full - no address available
                    self.log(f"[DEBUG CLUSTER_SIZE] CLUSTER_HEAD Node {self.id}: CLUSTER FULL! Cannot assign address to node {pck['gui']}")
                    self.log(f"[DEBUG CLUSTER_SIZE] CLUSTER_HEAD Node {self.id}: All addresses used - no JOIN_REPLY sent (node will retry or choose another parent)")
                    # No reply sent - node will retry or choose another parent
            if pck['type'] == 'NETWORK_REQUEST':  # it sends a network reply to requested node
                # yield self.timeout(.5)
                if self.role == Roles.ROOT:
                    # DEBUG: Check cluster network ID pool
                    self.log(f"[DEBUG CLUSTER_SIZE] ROOT Node {self.id}: Received NETWORK_REQUEST from {pck['source']}")
                    self.log(f"[DEBUG CLUSTER_SIZE] ROOT Node {self.id}: Current net_id pool - total={len(self.net_id_available_dict)}, used={sum(1 for v in self.net_id_available_dict.values() if v is not None)}, available={sum(1 for v in self.net_id_available_dict.values() if v is None)}")
                    
                    # Search for available network ID
                    avail_net_id = None
                    for net_id, avail in self.net_id_available_dict.items():
                        if avail is None or avail == pck['source']:
                            avail_net_id = net_id
                            break
                    
                    if avail_net_id is not None:
                        # Assign network ID
                        self.net_id_available_dict[avail_net_id] = pck['source']  # Mark as used
                        new_addr = wsn.Addr(avail_net_id, 254)
                        self.log(f"[DEBUG CLUSTER_SIZE] ROOT Node {self.id}: ASSIGNED cluster network ID {avail_net_id} to {pck['source']} (address={new_addr})")
                        self.log(f"[DEBUG CLUSTER_SIZE] ROOT Node {self.id}: net_id pool after assignment - used={sum(1 for v in self.net_id_available_dict.values() if v is not None)}/{len(self.net_id_available_dict)}")
                        self.send_network_reply(pck['source'], new_addr)
                    else:
                        self.log(f"[DEBUG CLUSTER_SIZE] ROOT Node {self.id}: ERROR - No available cluster network IDs! All {len(self.net_id_available_dict)} clusters are in use")
                        # Still send reply but log error
                        new_addr = wsn.Addr(pck['source'].node_addr, 254)
                        self.send_network_reply(pck['source'], new_addr)
            if pck['type'] == 'JOIN_ACK':
                self.members_table.append(pck['source'])
            if pck['type'] == 'NETWORK_UPDATE':
                self.child_networks_table[pck['gui']] = pck['child_networks']
                if self.role != Roles.ROOT:
                    self.send_network_update()
            if pck['type'] == 'I_AM_ORPHAN':  # if the sender is parent, starts repairing procedure
                # ROOT doesn't have a parent, so just log the orphan event
                self.log(f"[RECOVERY] ROOT Node {self.id}: Received I_AM_ORPHAN from node {pck.get('gui')}")
            if pck['type'] == 'NEIGHBOR_INFO_BROADCAST':
                # Process shared neighbor information: add discovered neighbors with incremented hop distance
                if self.role != Roles.ROOT:
                    for neighbor_id, neighbor_packet in pck['neighbors'].items():
                        if neighbor_id not in self.local_neighbor_map and neighbor_id != self.id:
                            neighbor_entry = neighbor_packet.copy()
                            neighbor_entry['mesh_hop_distance'] += 1
                            neighbor_entry['next_hop'] = pck['source']
                            self.local_neighbor_map[neighbor_id] = neighbor_entry
                            # Log DV_KSHARE
                            neighbor_addr = neighbor_entry.get('addr')
                            if neighbor_addr is not None:
                                via_addr = pck.get('source')
                                write_log(self.id, f"DV_KSHARE from={pck['gui']} tgt={neighbor_id} hop={neighbor_entry['mesh_hop_distance']} via={via_addr}", self.now)
                            if neighbor_entry['mesh_hop_distance'] > config.MAX_MESH_DISCOVERY_HOPS + 1:
                                raise Exception("Something went wrong")
            if pck['type'] == 'SENSOR_DATA':
                pass
                # self.log(str(pck['source'])+'--'+str(pck['sensor_value']))

        elif self.role == Roles.REGISTERED:  # if the node is registered
            if 'next_hop' in pck.keys() and pck['dest'] != self.addr and (self.ch_addr is None or pck['dest'] != self.ch_addr):  # forwards message if destination is not itself
                self.route_and_forward_package(pck)
                return
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'PROBE':
                # yield self.timeout(.5)
                self.send_heart_beat()
            if pck['type'] == 'JOIN_REQUEST':  # it sends a network request to the root
                self.received_JR_guis.append(pck['gui'])
                # yield self.timeout(.5)
                self.send_network_request() #this is getting spammed
            if pck['type'] == 'I_AM_ORPHAN':  # if the sender is parent, starts repairing procedure
                # Check if sender is our parent
                if self.parent_gui is not None and pck.get('gui') == self.parent_gui:
                    self.log(f"[RECOVERY] Node {self.id}: Received I_AM_ORPHAN from parent {self.parent_gui}, starting repair")
                    self.repair()
            if pck['type'] == 'NEIGHBOR_INFO_BROADCAST':
                # Process shared neighbor information: add discovered neighbors with incremented hop distance
                for neighbor_id, neighbor_packet in pck['neighbors'].items():
                    if neighbor_id not in self.local_neighbor_map and neighbor_id != self.id:
                        neighbor_entry = neighbor_packet.copy()
                        neighbor_entry['mesh_hop_distance'] += 1
                        neighbor_entry['next_hop'] = pck['source']
                        self.local_neighbor_map[neighbor_id] = neighbor_entry
                        # Log DV_KSHARE
                        neighbor_addr = neighbor_entry.get('addr')
                        if neighbor_addr is not None:
                            via_addr = pck.get('source')
                            write_log(self.id, f"DV_KSHARE from={pck['gui']} tgt={neighbor_id} hop={neighbor_entry['mesh_hop_distance']} via={via_addr}", self.now)
                        if neighbor_entry['mesh_hop_distance'] > config.MAX_MESH_DISCOVERY_HOPS + 1:
                            raise Exception("Something went wrong")
            if pck['type'] == 'NETWORK_REPLY':  # it becomes cluster head and send join reply to the candidates
                old_role = self.role
                self.set_role(Roles.CLUSTER_HEAD)
                # Log role change to CLUSTER_HEAD (already logged in set_role, but add context)
                if old_role != Roles.CLUSTER_HEAD:
                    self.log(f"[RECOVERY] Node {self.id}: Became CLUSTER_HEAD at {self.now:.3f}")
                check_all_nodes_registered()
                try:
                    write_clusterhead_distances_csv("clusterhead_distances.csv")
                except Exception as e:
                    self.log(f"CH CSV export error: {e}")
                self.scene.nodecolor(self.id, 0, 0, 1)
                self.ch_addr = pck['addr']
                
                # Set cluster tx_power from NETWORK_REPLY
                if 'tx_power' in pck:
                    self.assign_tx_power(pck['tx_power'])
                else:
                    # Fallback to default if not provided
                    self.assign_tx_power(config.NODE_DEFAULT_TX_POWER)
                
                # Initialize address pool for new CLUSTER_HEAD
                self.node_available_dict = {i: None for i in range(1, config.NUM_OF_CHILDREN+1)}
                self.log(f"[DEBUG CLUSTER_SIZE] NEW CLUSTER_HEAD Node {self.id}: Initialized address pool - NUM_OF_CHILDREN={config.NUM_OF_CHILDREN}, pool_size={len(self.node_available_dict)}")
                self.log(f"[DEBUG CLUSTER_SIZE] CLUSTER_HEAD Node {self.id}: Cluster address={self.ch_addr}, can accept up to {config.NUM_OF_CHILDREN} child nodes")
                self.send_network_update()
                self.send_heart_beat()
                # Set up neighbor checking timer
                self.set_timer('TIMER_CHECK_NEIGHBORS', config.HEART_BEAT_TIME_INTERVAL * 2)
                # Process pending join requests
                self.log(f"[DEBUG CLUSTER_SIZE] CLUSTER_HEAD Node {self.id}: Processing {len(self.received_JR_guis)} pending join requests")
                for gui in self.received_JR_guis:
                    # yield self.timeout(random.uniform(.1,.5))
                    # Search for available address
                    avail_node_id = None
                    for node_id, avail in self.node_available_dict.items():
                        if avail is None or avail == gui:
                            avail_node_id = node_id
                            break
                    
                    if avail_node_id is not None:
                        self.node_available_dict[avail_node_id] = gui  # Mark as used
                        assigned_addr = wsn.Addr(self.ch_addr.net_addr, avail_node_id)
                        self.log(f"[DEBUG CLUSTER_SIZE] CLUSTER_HEAD Node {self.id}: ASSIGNED address {assigned_addr} to pending node {gui} (node_id={avail_node_id})")
                        self.send_join_reply(gui, assigned_addr)
                    else:
                        self.log(f"[DEBUG CLUSTER_SIZE] CLUSTER_HEAD Node {self.id}: WARNING - No address available for pending node {gui} (should not happen on initialization)")
                        # Still send reply with GUI as node_id (fallback)
                        self.send_join_reply(gui, wsn.Addr(self.ch_addr.net_addr, gui))

        elif self.role == Roles.UNDISCOVERED:  # if the node is undiscovered
            if pck['type'] == 'HEART_BEAT':  # it kills probe timer, becomes unregistered and sets join request timer once received heart beat
                self.update_neighbor(pck)
                self.kill_timer('TIMER_PROBE')
                self.become_unregistered()

        if self.role == Roles.UNREGISTERED:  # if the node is unregistered
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'JOIN_REPLY':  # it becomes registered and sends join ack if the message is sent to itself once received join reply
                if pck['dest_gui'] == self.id:
                    self.addr = pck['addr']
                    self.parent_gui = pck['gui']
                    self.root_addr = pck['root_addr']
                    self.hop_count = pck['hop_count']
                    
                    # Set cluster tx_power from JOIN_REPLY
                    if 'tx_power' in pck:
                        self.assign_tx_power(pck['tx_power'])
                    else:
                        # Fallback: use smart selection if enabled, else default
                        if config.ALLOW_TX_POWER_CHOICE:
                            self.assign_tx_power()  # Smart selection based on distance to parent
                        else:
                            self.assign_tx_power(config.NODE_DEFAULT_TX_POWER)
                    
                    self.draw_parent()
                    self.kill_timer('TIMER_JOIN_REQUEST')
                    self.send_heart_beat()
                    self.set_timer('TIMER_HEART_BEAT', config.HEART_BEAT_TIME_INTERVAL)
                    # Set up neighbor checking timer
                    self.set_timer('TIMER_CHECK_NEIGHBORS', config.HEART_BEAT_TIME_INTERVAL * 2)
                    self.set_timer('TIMER_SENSOR', config.DATA_INTERVAL)
                    self.send_join_ack(pck['source'])
                    if self.ch_addr is not None: # it could be a cluster head which lost its parent
                        self.set_role(Roles.CLUSTER_HEAD)
                        self.send_network_update()
                    else:
                        self.set_role(Roles.REGISTERED)
                        self.register()
                        check_all_nodes_registered()
                        #check if all nodes are registered
                        
                        self.set_timer('TIMER_NEIGHBOR_BROADCAST', config.NEIGHBOR_INFO_BROADCAST_INTERVAL)
                        # Log joining network event
                        if self.was_orphan:
                            log_join_network(self.id, self.now, "recovered_from_orphan")
                            if self.id in ORPHAN_NODES:
                                ORPHAN_NODES.remove(self.id)
                            self.was_orphan = False
                        else:
                            log_join_network(self.id, self.now, "initial_join")

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
            self.wake_up_time = self.now #measure time when powered on
            self.set_timer('TIMER_PROBE', 1)

        elif name == 'TIMER_PROBE':  # it sends probe if counter didn't reach the threshold once timer probe fired.
            if self.c_probe < self.th_probe:
                self.send_probe()
                self.c_probe += 1
                self.set_timer('TIMER_PROBE', 1)
            else:  # if the counter reached the threshold
                if self.is_root_eligible:  # if the node is root eligible, it becomes root
                    self.set_role(Roles.ROOT)
                    self.scene.nodecolor(self.id, 0, 0, 0)
                    self.addr = wsn.Addr(0, 254)
                    self.ch_addr = wsn.Addr(0, 254)
                    self.root_addr = self.addr
                    self.hop_count = 0
                    # Set ROOT tx_power (always use default/max power)
                    self.assign_tx_power(config.NODE_DEFAULT_TX_POWER)
                    
                    # Initialize address pools for ROOT
                    self.net_id_available_dict = {i: None for i in range(1, config.NUM_OF_CLUSTERS+1)}
                    self.node_available_dict = {i: None for i in range(1, config.NUM_OF_CHILDREN+1)}
                    self.log(f"[DEBUG CLUSTER_SIZE] ROOT Node {self.id}: Initialized address pools - NUM_OF_CLUSTERS={config.NUM_OF_CLUSTERS}, NUM_OF_CHILDREN={config.NUM_OF_CHILDREN}")
                    self.log(f"[DEBUG CLUSTER_SIZE] ROOT Node {self.id}: node_available_dict size={len(self.node_available_dict)}, available={sum(1 for v in self.node_available_dict.values() if v is None)}")
                    self.log(f"[DEBUG CLUSTER_SIZE] ROOT Node {self.id}: net_id_available_dict size={len(self.net_id_available_dict)}, available={sum(1 for v in self.net_id_available_dict.values() if v is None)}")

                    self.set_timer('TIMER_HEART_BEAT', config.HEART_BEAT_TIME_INTERVAL)
                    # Set up neighbor checking timer
                    self.set_timer('TIMER_CHECK_NEIGHBORS', config.HEART_BEAT_TIME_INTERVAL * 2)
                else:  # otherwise it keeps trying to sending probe after a long time
                    self.c_probe = 0
                    self.set_timer('TIMER_PROBE', 30)

        elif name == 'TIMER_HEART_BEAT':  # it sends heart beat message once heart beat timer fired
            if not self.is_failed:  # Only send heartbeat if node is not failed
                self.send_heart_beat()
                self.set_timer('TIMER_HEART_BEAT', config.HEART_BEAT_TIME_INTERVAL)
            # Check for dead neighbors and handle failures
            self.check_neighbors()
        #elif name == "NET_REQ_TIMEOUT": #check if we are a clusterhead yet, if we are, cancel timer, else, resend
        #    self.log("TIMEOUT")
        #    if self.role == Roles.CLUSTER_HEAD or self.role == Roles.ROOT:
        #        self.kill_timer("NET_REQ_TIMEOUT")
        #    else:
        #        self.send_network_request()
        #        self.set_timer("NET_REQ_TIMEOUT", config.SLEEP_MODE_PROBE_TIME_INTERVAL)
        elif name == 'TIMER_JOIN_REQUEST':  # if it has not received heart beat messages before, it sets timer again and wait heart beat messages once join request timer fired.
            if len(self.candidate_parents_table) == 0:
                # Check if we're orphaned
                if self.parent_gui is not None and self.parent_gui in FAILED_NODES:
                    self.log(f"[RECOVERY] Node {self.id}: Detected orphan status (parent {self.parent_gui} failed)")
                    log_orphan_event(self.id, self.now, f"parent_failed:{self.parent_gui}")
                    ORPHAN_NODES.add(self.id)
                    self.was_orphan = True
                self.become_unregistered()
            else:  # otherwise it chose one of them and sends join request
                self.select_and_join()
        elif name == 'TIMER_CHECK_NEIGHBORS':  # Periodic check for dead neighbors
            self.check_neighbors()
            self.set_timer('TIMER_CHECK_NEIGHBORS', config.HEART_BEAT_TIME_INTERVAL * 2)
        elif name == 'TIMER_NODE_FAILURE':  # Node failure event
            self.fail_node()
        elif name == 'TIMER_NODE_RECOVERY':  # Node recovery event
            self.recover_node()
        elif name == 'TIMER_NEIGHBOR_BROADCAST':
            self.broadcast_neighbor_info()
            self.set_timer('TIMER_NEIGHBOR_BROADCAST', config.NEIGHBOR_INFO_BROADCAST_INTERVAL)
        elif name == 'TIMER_SENSOR':
            self.send_sensor_data()
            self.set_timer('TIMER_SENSOR', config.DATA_INTERVAL)
        #elif name == 'TIMER_SENSOR':
        #    self.route_and_forward_package({'dest': self.root_addr, 'type': 'SENSOR', 'source': self.addr, 'sensor_value': random.uniform(10,50)})
        #    timer_duration =  self.id % 20
        #    if timer_duration == 0: timer_duration = 1
        #    self.set_timer('TIMER_SENSOR', timer_duration)
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



ROOT_ID = 1  # 0..count-1



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
with open("packet_routes.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["time", "packet_type", "source", "current_node", "next_hop", "dest", "hop_count", "path_type"])

# Initialize packet_delays.csv
with open("packet_delays.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["packet_type", "source", "source_gui", "dest", "dest_gui", "created_at", "delivered_at", "delay"])

def log_packet_delivery(pck, receiver_node, path="packet_delays.csv"):
    """Log end-to-end delivery delay for packets that reach their final destination.
    
    Args:
        pck (Dict): Packet that reached final destination, should contain 'created_at', 'type', 'source', 'dest'
        receiver_node (SensorNode): Node that received the packet (final destination)
        path (str): Path to packet_delays.csv file
    """
    try:
        created_at = pck.get('created_at')
        if created_at is None:
            # Skip if packet doesn't have creation timestamp
            return
        
        delivered_at = receiver_node.now
        delay = delivered_at - created_at
        
        # Get packet information
        ptype = pck.get('type', '')
        src = pck.get('source', '')
        dest = pck.get('dest', '')
        src_gui = pck.get('gui', '')  # Source GUI if available
        dest_gui = receiver_node.id  # Destination GUI
        
        # Log to CSV
        with open(path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                ptype,
                str(src),
                src_gui,
                str(dest),
                dest_gui,
                f"{created_at:.6f}",
                f"{delivered_at:.6f}",
                f"{delay:.6f}"
            ])
    except Exception as e:
        # Silently fail to avoid disrupting simulation
        pass

def log_packet_route(pck, current_node, next_hop, path):
    """Append a routing trace row to packet_routes.csv."""
    with open("packet_routes.csv", "a", newline="") as f:
        w = csv.writer(f)
        # Write header only if file is empty
        if f.tell() == 0:
            w.writerow(["time", "packet_type", "source", "current_node", "next_hop", "dest", "hop_count", "routing_direction"])
        # Get readable values
        time = getattr(current_node, "now", "")
        ptype = pck.get("type", "")
        src = str(pck.get("source", ""))
        dest = str(pck.get("dest", ""))
        hop = pck.get("hop_count", "")
        w.writerow([time, ptype, src, current_node.id, next_hop, dest, hop, path])

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
                    "neighbor_role", "mesh_hop_distance", "arrival_time"])

        for node in sim.nodes:
            # Skip nodes without any neighbor info yet
            if not hasattr(node, "local_neighbor_map"):
                continue

            x1, y1 = NODE_POS.get(node.id, (None, None))
            if x1 is None:
                continue  # no position → cannot compute distance

            # local_neighbor_map: key = neighbor GUI, value = heartbeat packet dict
            for n_gui, pck in getattr(node, "local_neighbor_map", {}).items():
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
                hop = pck.get("mesh_hop_distance", "")
                at  = pck.get("arrival_time", "")

                w.writerow([node.id, n_gui, f"{dist:.6f}", n_role, hop, at])

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
        # Set initial tx_range using default power level
        node.assign_tx_power(config.NODE_DEFAULT_TX_POWER)
        node.log(f"[DEBUG TX_POWER] Node {node.id}: Initialized with default tx_power={node.tx_power}, tx_range={node.tx_range:.2f}m")
        node.logging = True
        node.arrival = random.uniform(0, config.NODE_ARRIVAL_MAX)
        if node.id == ROOT_ID:
            node.arrival = 0.1


# Initialize log file before creating network
log_filename = init_log_file()
print(f"Logging to {log_filename}")

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

# Initialize recovery tracking CSV files
with open("recovery_events.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["node_id", "failure_time", "recovery_time", "recovery_duration", "orphan_count_at_recovery"])

with open("orphan_events.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["node_id", "time", "reason"])

with open("role_changes.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["node_id", "old_role", "new_role", "time"])

with open("join_network_events.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["node_id", "time", "join_type"])

# Schedule random node failures if enabled
if config.ENABLE_NODE_FAILURE:
    def schedule_node_failures():
        """Schedule random node failures."""
        if config.NUM_NODES_TO_FAIL > 0 and config.NUM_NODES_TO_FAIL < len(ALL_NODES):
            # Select random nodes to fail (excluding ROOT)
            nodes_to_fail = random.sample(
                [n for n in ALL_NODES if n.id != ROOT_ID and not n.is_failed],
                min(config.NUM_NODES_TO_FAIL, len([n for n in ALL_NODES if n.id != ROOT_ID]))
            )
            
            for i, node in enumerate(nodes_to_fail):
                failure_time = config.NODE_FAILURE_START_TIME + (i * config.NODE_FAILURE_INTERVAL)
                recovery_time = failure_time + config.NODE_RECOVERY_TIME
                
                # Schedule failure
                sim.delayed_exec(failure_time - sim.now, lambda n=node: n.fail_node())
                
                # Schedule recovery
                sim.delayed_exec(recovery_time - sim.now, lambda n=node: n.recover_node())
                
                write_log(None, f"FAILURE_SCHEDULED node={node.id} failure_time={failure_time:.3f} recovery_time={recovery_time:.3f}", sim.now)
                print(f"[FAILURE] Scheduled node {node.id} to fail at {failure_time:.3f} and recover at {recovery_time:.3f}")
    
    # Schedule failures after network is created
    sim.delayed_exec(10, schedule_node_failures)

# start the simulation
sim.run()
log_all_nodes_registered()
calculate_and_log_average_join_time()
calculate_and_log_average_packet_delay()

# Write recovery statistics
def write_recovery_statistics():
    """Write recovery statistics to CSV files."""
    # Write recovery events
    with open("recovery_events.csv", "a", newline="") as f:
        writer = csv.writer(f)
        for event in RECOVERY_EVENTS:
            writer.writerow([
                event['node_id'],
                f"{event['failure_time']:.6f}",
                f"{event['recovery_time']:.6f}",
                f"{event['recovery_duration']:.6f}",
                event['orphan_count']
            ])
    
    # Write orphan events
    with open("orphan_events.csv", "a", newline="") as f:
        writer = csv.writer(f)
        for event in ORPHAN_EVENTS:
            writer.writerow([
                event['node_id'],
                f"{event['time']:.6f}",
                event['reason']
            ])
    
    # Write role changes
    with open("role_changes.csv", "a", newline="") as f:
        writer = csv.writer(f)
        for event in ROLE_CHANGE_EVENTS:
            writer.writerow([
                event['node_id'],
                event['old_role'],
                event['new_role'],
                f"{event['time']:.6f}"
            ])
    
    # Calculate and print recovery statistics
    if RECOVERY_EVENTS:
        recovery_durations = [e['recovery_duration'] for e in RECOVERY_EVENTS]
        avg_recovery_time = sum(recovery_durations) / len(recovery_durations)
        min_recovery_time = min(recovery_durations)
        max_recovery_time = max(recovery_durations)
        
        print(f"\n{'='*60}")
        print(f"📊 NETWORK RECOVERY STATISTICS")
        print(f"{'='*60}")
        print(f"Total recovery events: {len(RECOVERY_EVENTS)}")
        print(f"Average recovery time: {avg_recovery_time:.6f} simulation time units")
        print(f"Minimum recovery time: {min_recovery_time:.6f} simulation time units")
        print(f"Maximum recovery time: {max_recovery_time:.6f} simulation time units")
        print(f"Total orphan events: {len(ORPHAN_EVENTS)}")
        print(f"Total role changes: {len(ROLE_CHANGE_EVENTS)}")
        print(f"Current orphan nodes: {len(ORPHAN_NODES)}")
        if ORPHAN_NODES:
            print(f"Orphan node IDs: {sorted(ORPHAN_NODES)}")
        print(f"{'='*60}\n")
        
        # Write summary
        with open("recovery_summary.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value"])
            writer.writerow(["total_recovery_events", len(RECOVERY_EVENTS)])
            writer.writerow(["average_recovery_time", f"{avg_recovery_time:.6f}"])
            writer.writerow(["min_recovery_time", f"{min_recovery_time:.6f}"])
            writer.writerow(["max_recovery_time", f"{max_recovery_time:.6f}"])
            writer.writerow(["total_orphan_events", len(ORPHAN_EVENTS)])
            writer.writerow(["total_role_changes", len(ROLE_CHANGE_EVENTS)])
            writer.writerow(["current_orphan_count", len(ORPHAN_NODES)])
        
        print(f"✅ Recovery statistics saved to recovery_summary.csv")
    else:
        print(f"\n⚠️ No recovery events occurred during simulation")

write_recovery_statistics()
close_log_file()
print("Simulation Finished")


# Created 100 nodes at random locations with random arrival times.
# When nodes are created they appear in white
# Activated nodes becomes red
# Discovered nodes will be yellow
# Registered nodes will be green.
# Root node will be black.
# Routers/Cluster Heads should be blue