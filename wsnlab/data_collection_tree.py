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

def _addr_str(a): return "" if a is None else str(a)
def _role_name(r): return r.name if hasattr(r, "name") else str(r)


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

    def set_role(self, new_role, *, recolor=True):
        """Central place to switch roles, keep tallies, and (optionally) recolor."""
        old_role = getattr(self, "role", None)
        if old_role is not None:
            ROLE_COUNTS[old_role] -= 1
            if ROLE_COUNTS[old_role] <= 0:
                ROLE_COUNTS.pop(old_role, None)
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
    def update_neighbor(self, pck):
        pck['arrival_time'] = self.now
        # compute Euclidean distance between self and neighbor
        if pck['gui'] in NODE_POS and self.id in NODE_POS:
            x1, y1 = NODE_POS[self.id]
            x2, y2 = NODE_POS[pck['gui']]
            pck['distance'] = math.hypot(x1 - x2, y1 - y2)
        pck['mesh_hop_distance'] = 1
        self.local_neighbor_map[pck['gui']] = pck

        if pck.get('addr') is not None:
            if pck['gui'] not in self.child_networks_table.keys() or pck['addr'] not in self.members_table:
                if pck["gui"] not in self.candidate_parents_table:
                    self.candidate_parents_table.append(pck["gui"])
        
        # Log node state after neighbor update
        log_node_state(self, from_node_id=pck.get('gui'))

    ###################
    def select_and_join(self):
        min_hop = 99999
        min_hop_gui = 99999
        for gui in self.candidate_parents_table:
            if self.local_neighbor_map[gui]['hop_count'] < min_hop or (self.local_neighbor_map[gui]['hop_count'] == min_hop and gui < min_hop_gui):
                min_hop = self.local_neighbor_map[gui]['hop_count']
                min_hop_gui = gui
        selected_addr = self.local_neighbor_map[min_hop_gui]['source']
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
        pck = {'dest': wsn.BROADCAST_ADDR, 'type': 'JOIN_REPLY', 'source': self.ch_addr,
                   'gui': self.id, 'dest_gui': gui, 'addr': addr, 'root_addr': self.root_addr,
                   'hop_count': self.hop_count+1, 'created_at': self.now}
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
        pck = {'dest': dest, 'type': 'NETWORK_REPLY', 'source': self.addr, 'addr': addr, 'created_at': self.now}
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
                # yield self.timeout(.5)
                avail_node_id = None
                for node_id, avail in self.node_available_dict.items():
                    if avail is None or avail == pck['gui']:
                        avail_node_id = node_id
                        break
                if avail_node_id is not None and self.ch_addr is not None:
                    self.node_available_dict[avail_node_id] = pck['gui'] #this network is now being used
                    self.send_join_reply(pck['gui'], wsn.Addr(self.ch_addr.net_addr, avail_node_id))
                # else: cluster is full, no reply sent (node will retry or choose another parent)
            if pck['type'] == 'NETWORK_REQUEST':  # it sends a network reply to requested node
                # yield self.timeout(.5)
                if self.role == Roles.ROOT:
                    avail_net_id = None
                    for net_id, avail in self.net_id_available_dict.items():
                        if avail is None or avail == pck['source']:
                            avail_net_id = net_id
                            break
                    if avail_net_id is None:
                        print("BUG")
                        print(self.net_id_available_dict)
                        self.log(pck)
                    new_addr = wsn.Addr(avail_net_id,254)
                    self.net_id_available_dict[avail_net_id] = pck['source'] #this network is now being used
                    self.send_network_reply(pck['source'],new_addr)
            if pck['type'] == 'JOIN_ACK':
                self.members_table.append(pck['source'])
            if pck['type'] == 'NETWORK_UPDATE':
                self.child_networks_table[pck['gui']] = pck['child_networks']
                if self.role != Roles.ROOT:
                    self.send_network_update()
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
                self.set_role(Roles.CLUSTER_HEAD)
                check_all_nodes_registered()
                try:
                    write_clusterhead_distances_csv("clusterhead_distances.csv")
                except Exception as e:
                    self.log(f"CH CSV export error: {e}")
                self.scene.nodecolor(self.id, 0, 0, 1)
                self.ch_addr = pck['addr']
                self.send_network_update()
                self.node_available_dict = {i: None for i in range(1, config.NUM_OF_CHILDREN+1)} #what we will need to add for this to be stable is the reopening of a lost network, but we get there when we get there

                # yield self.timeout(.5)
                self.send_heart_beat()
                for gui in self.received_JR_guis:
                    # yield self.timeout(random.uniform(.1,.5))
                    avail_node_id = None
                    for node_id, avail in self.node_available_dict.items():
                        if avail is None or avail == gui:
                            avail_node_id = node_id
                            break
                    if avail_node_id is not None:
                        self.node_available_dict[avail_node_id] = gui#this network is now being used
                        self.send_join_reply(gui, wsn.Addr(self.ch_addr.net_addr,avail_node_id))
                    # else: cluster is full, skip this join request

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
                    self.draw_parent()
                    self.kill_timer('TIMER_JOIN_REQUEST')
                    self.send_heart_beat()
                    self.set_timer('TIMER_HEART_BEAT', config.HEART_BEAT_TIME_INTERVAL)
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
                    self.net_id_available_dict = {i: None for i in range(1, config.NUM_OF_CLUSTERS)} #what we will need to add for this to be stable is the reopening of a lost network, but we get there when we get there
                    self.node_available_dict = {i: None for i in range(1, config.NUM_OF_CHILDREN+1)} #what we will need to add for this to be stable is the reopening of a lost network, but we get there when we get there

                    self.set_timer('TIMER_HEART_BEAT', config.HEART_BEAT_TIME_INTERVAL)
                else:  # otherwise it keeps trying to sending probe after a long time
                    self.c_probe = 0
                    self.set_timer('TIMER_PROBE', 30)

        elif name == 'TIMER_HEART_BEAT':  # it sends heart beat message once heart beat timer fired
            self.send_heart_beat()
            self.set_timer('TIMER_HEART_BEAT', config.HEART_BEAT_TIME_INTERVAL)
            #print(self.id)
        #elif name == "NET_REQ_TIMEOUT": #check if we are a clusterhead yet, if we are, cancel timer, else, resend
        #    self.log("TIMEOUT")
        #    if self.role == Roles.CLUSTER_HEAD or self.role == Roles.ROOT:
        #        self.kill_timer("NET_REQ_TIMEOUT")
        #    else:
        #        self.send_network_request()
        #        self.set_timer("NET_REQ_TIMEOUT", config.SLEEP_MODE_PROBE_TIME_INTERVAL)
        elif name == 'TIMER_JOIN_REQUEST':  # if it has not received heart beat messages before, it sets timer again and wait heart beat messages once join request timer fired.
            if len(self.candidate_parents_table) == 0:
                self.become_unregistered()
            else:  # otherwise it chose one of them and sends join request
                self.select_and_join()
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
        node.tx_range = config.NODE_TX_RANGE * config.SCALE
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

# start the simulation
sim.run()
log_all_nodes_registered()
calculate_and_log_average_join_time()
calculate_and_log_average_packet_delay()
close_log_file()
print("Simulation Finished")


# Created 100 nodes at random locations with random arrival times.
# When nodes are created they appear in white
# Activated nodes becomes red
# Discovered nodes will be yellow
# Registered nodes will be green.
# Root node will be black.
# Routers/Cluster Heads should be blue