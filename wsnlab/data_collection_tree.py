import random
from enum import Enum
import sys
sys.path.insert(1, '.')
from source import wsnlab_vis as wsn
import math
from source import config
from collections import Counter
import os
import hashlib


import csv  # <— add this near your other imports

# Track where each node is placed
NODE_POS = {}  # {node_id: (x, y)}

# --- tracking containers ---
ALL_NODES = []              # node objects
CLUSTER_HEADS = []
ROLE_COUNTS = Counter()     # live tally per Roles enum

def _addr_str(a): return "" if a is None else str(a)
def _role_name(r): return r.name if hasattr(r, "name") else str(r)


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
        self.set_role(Roles.UNDISCOVERED)
        self.is_root_eligible = True if self.id == ROOT_ID else False
        self.c_probe = 0  # c means counter and probe is the name of counter
        self.th_probe = 10  # th means threshold and probe is the name of threshold
        self.hop_count = 99999
        self.neighbors_table = {}  # keeps neighbor information with received HB messages
        self.candidate_parents_table = []
        self.child_networks_table = {}
        self.members_table = []
        self.received_JR_guis = []  # keeps received Join Request global unique ids
        #KG- neighbor discovery (multi-hop)
        #KG- direct next-hops to neighbors discovered via heartbeats
        self.one_hop_next = {}     # gui -> next-hop Addr (direct neighbor)
        #KG- two-hop next-hops learned by neighbor-table sharing
        self.two_hop_next = {}     # gui -> next-hop Addr (via a neighbor)

        # --- NEW: generalized K-hop neighbor map ---
        # gui -> {'next_hop': Addr, 'hop': int}
        self.k_hop_next = {}
        # How far to propagate (and keep) neighbor info. If not set in config.py, default to 3.
        self.k_max = getattr(config, 'NEIGHBOR_K_MAX', 3)

        #KG- debug controls
        self.debug_enabled = getattr(config, 'DEBUG', False)
        self.debug_log_path = getattr(config, 'DEBUG_LOG_PATH', 'wsn_debug.log')

        # optional delay model config and state
        self.delay_model = getattr(config, 'ENABLE_DELAY_MODEL', False)
        self.proc_delay_mean = getattr(config, 'PROC_DELAY_MEAN', 0.0)
        self.tx_delay_per_hop = getattr(config, 'TX_DELAY_PER_HOP', 0.0)
        self.tx_delay_jitter = getattr(config, 'TX_DELAY_JITTER', 0.0)
        self._tx_pending = []          # list of (send_time, packet_dict)
        self._tx_timer_armed = False

    ###################
    def run(self):
        """Setting the arrival timer to wake up after firing.

        Args:

        Returns:

        """
        self.set_timer('TIMER_ARRIVAL', self.arrival)

    ###################

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
        self.neighbors_table = {}
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
        self.neighbors_table[pck['gui']] = pck
        #KG- learn direct next-hop for this neighbor (1-hop)
        if 'addr' in pck:
            self.one_hop_next[pck['gui']] = pck['addr']
        #KG- learn two-hop via neighbor's neighbor list (shared in heartbeat)
        for n2 in pck.get('nbrs', []) or []:
            if 'addr' in pck:
                self.two_hop_next[n2] = pck['addr']

        # --- K-hop neighbor map merge ---
        # A) Neighbor itself at hop=1 (via its addr)
        try:
            nh = pck.get('addr')
            if nh is not None:
                cur = self.k_hop_next.get(pck['gui'])
                if cur is None or cur.get('hop', 1e9) > 1:
                    self.k_hop_next[pck['gui']] = {'next_hop': nh, 'hop': 1}
        except Exception:
            pass

        # B) Legacy 2-hop from 'nbrs' → our hop=2 (if enabled by K)
        for n2 in pck.get('nbrs', []) or []:
            via = nh
            if via is None:
                continue
            cur = self.k_hop_next.get(n2)
            if cur is None or 2 < cur.get('hop', 1e9):
                if 2 <= self.k_max:
                    self.k_hop_next[n2] = {'next_hop': via, 'hop': 2}

        # C) General K-map: pck shares (tgt, h). We adopt (h+1) via neighbor.
        for tgt, h in (pck.get('nbrs_k', {}) or {}).items():
            try:
                hh = int(h)
            except Exception:
                continue
            via = nh
            if via is None:
                continue
            cand_h = hh + 1
            if cand_h > self.k_max:
                continue
            if tgt == self.id:
                continue  # ignore self
            cur = self.k_hop_next.get(tgt)
            if cur is None or cand_h < cur.get('hop', 1e9):
                self.k_hop_next[tgt] = {'next_hop': via, 'hop': cand_h}
                self._dbg(f"DV_KSHARE from={pck['gui']} tgt={tgt} hop={cand_h} via={_addr_str(via)}")

        if (pck['gui'] not in self.child_networks_table) and (pck['gui'] not in self.members_table):
            if pck['gui'] not in self.candidate_parents_table:
                self.candidate_parents_table.append(pck['gui'])
        #KG- optional debug dump
        if getattr(self, 'debug_enabled', False):
            try:
                with open(self.debug_log_path, 'a') as f:
                    # Simple, single-line snapshot with key fields
                    # [time] N<me> from=<src> role=<role> hop=<my_hop> parent=<pg> neighs=<count>(<ids>) 1hop=<ids> 2hop=<ids>
                    one_ids = ",".join(str(g) for g in sorted(self.one_hop_next.keys()))
                    two_ids = ",".join(str(g) for g in sorted(self.two_hop_next.keys()))
                    n_ids  = ",".join(str(g) for g in sorted(self.neighbors_table.keys()))
                    f.write(
                        f"[{self.now:10.5f}] N{self.id} from={pck['gui']} role={_role_name(self.role)} "
                        f"hop={self.hop_count} parent={self.parent_gui} "
                        f"neighs={len(self.neighbors_table)}({n_ids or '-'}) "
                        f"1hop={one_ids or '-'} 2hop={two_ids or '-'}\n"
                    )
            except Exception:
                pass

    ###################
    def _dbg(self, line):
        """KG- append a single-line debug message if debug is enabled."""
        if not getattr(self, 'debug_enabled', False):
            return
        try:
            with open(self.debug_log_path, 'a') as f:
                f.write(f"[{self.now:10.5f}] N{self.id} {line}\n")
        except Exception:
            pass

    def _tx_enqueue(self, pck, delay):
        try:
            send_at = self.now + max(0.0, delay)
            self._tx_pending.append((send_at, pck))
            try:
                self._dbg(f"TX_ENQUEUE type={pck.get('type')} next={_addr_str(pck.get('next_hop'))} delay={max(0.0, delay):.3f} send_at={send_at:.3f}")
            except Exception:
                pass
            # arm timer to the soonest item
            if not self._tx_timer_armed:
                self.set_timer('TIMER_TX_SEND', max(0.01, delay))
                self._tx_timer_armed = True
            else:
                # if a sooner item appeared, re-arm earlier
                soonest = min(t for t, _ in self._tx_pending) if self._tx_pending else self.now
                delta = max(0.01, soonest - self.now)
                self.set_timer('TIMER_TX_SEND', delta)
        except Exception:
            pass

    def _tx_drain_due(self):
        """Send all packets whose send_time <= now; re-arm if more remain."""
        try:
            now = self.now
            due, future = [], []
            for t, p in self._tx_pending:
                (due if t <= now else future).append((t, p))
            self._tx_pending = future
            for _, pck in due:
                # TTL/self-hop guards were already applied in _prepare_and_send
                try:
                    self._dbg(f"TX_SEND type={pck.get('type')} next={_addr_str(pck.get('next_hop'))}")
                except Exception:
                    pass
                self.send(pck)
            if self._tx_pending:
                soonest = min(t for t, _ in self._tx_pending)
                self.set_timer('TIMER_TX_SEND', max(0.01, soonest - now))
                self._tx_timer_armed = True
            else:
                self._tx_timer_armed = False
        except Exception:
            self._tx_timer_armed = False

    ###################
    def _prepare_and_send(self, pck):
        """KG- Enforce TTL and no-progress loop guards before sending routed packets."""
        try:
            # stamp creation time if missing
            if 'created_at' not in pck:
                pck['created_at'] = self.now
                try:
                    self._dbg(f"STAMP created_at type={pck.get('type')} dest={_addr_str(pck.get('dest'))} ts={self.now:.3f}")
                except Exception:
                    pass
            # Initialize or decrement TTL for directed packets
            if pck.get('dest') not in (None, wsn.BROADCAST_ADDR):
                if 'ttl' not in pck:
                    # default ttl scales with k_max
                    pck['ttl'] = max(8, 2 * int(getattr(self, 'k_max', 3)))
                else:
                    pck['ttl'] -= 1
                    if pck['ttl'] <= 0:
                        self._dbg(f"DROP ttl0 type={pck.get('type')} dest={_addr_str(pck.get('dest'))}")
                        return

                # no-progress: avoid forwarding to self or repeating same hop
                nh = pck.get('next_hop')
                if nh == self.addr:
                    self._dbg(f"DROP self_next_hop type={pck.get('type')} dest={_addr_str(pck.get('dest'))}")
                    return
                if nh == self.ch_addr and pck.get('dest') != self.ch_addr:
                    self._dbg(f"DROP ch_next_hop_but_not_dest type={pck.get('type')} dest={_addr_str(pck.get('dest'))}")
                    return
                if pck.get('last_hop') == self.addr:
                    self._dbg(f"DROP repeat_hop type={pck.get('type')} dest={_addr_str(pck.get('dest'))}")
                    return
                # require next_hop for directed packets not for me
                if (pck.get('dest') != self.addr and pck.get('dest') != self.ch_addr) and nh is None:
                    self._dbg(f"DROP no_next_hop type={pck.get('type')} dest={_addr_str(pck.get('dest'))}")
                    return

                pck['last_hop'] = self.addr
        except Exception:
            # never crash on guard
            pass

        if getattr(self, 'delay_model', False):
            # simple per-hop model: processing + tx + jitter
            d = float(getattr(self, 'proc_delay_mean', 0.0)) + float(getattr(self, 'tx_delay_per_hop', 0.0))
            j = float(getattr(self, 'tx_delay_jitter', 0.0))
            if j > 0:
                d += random.uniform(-j, j)
            self._tx_enqueue(pck, max(0.0, d))
        else:
            try:
                self._dbg(f"TX_IMMEDIATE type={pck.get('type')} next={_addr_str(pck.get('next_hop'))}")
            except Exception:
                pass
            self.send(pck)

    ###################
    def select_and_join(self):
        min_hop = 99999
        min_hop_gui = 99999
        for gui in self.candidate_parents_table:
            if self.neighbors_table[gui]['hop_count'] < min_hop or (self.neighbors_table[gui]['hop_count'] == min_hop and gui < min_hop_gui):
                min_hop = self.neighbors_table[gui]['hop_count']
                min_hop_gui = gui
        selected_addr = self.neighbors_table[min_hop_gui]['source']
        self.send_join_request(selected_addr)
        self.set_timer('TIMER_JOIN_REQUEST', 5)


    ###################
    def send_probe(self):
        """Sending probe message to be discovered and registered.

        Args:

        Returns:

        """
        # mark join start time on first probe
        if not hasattr(self, '_join_started_at') or self._join_started_at is None:
            self._join_started_at = self.now
        try:
            self._dbg(f"PKT_CREATE type=PROBE created_at={self.now:.3f}")
        except Exception:
            pass
        self.send({'dest': wsn.BROADCAST_ADDR, 'type': 'PROBE', 'created_at': self.now})

    ###################
    def send_heart_beat(self):
        """Sending heart beat message

        Args:

        Returns:

        """
        #KG- compute my immediate neighbors (1-hop) by distance threshold for table sharing
        my_neighbors = []
        try:
            if self.id in NODE_POS:
                x1, y1 = NODE_POS[self.id]
                for gui, (x2, y2) in NODE_POS.items():
                    if gui == self.id:
                        continue
                    if math.hypot(x1 - x2, y1 - y2) <= self.tx_range:
                        my_neighbors.append(gui)
        except Exception:
            my_neighbors = []

        #KG- Build K-1 hop share map (receiver will +1 on receive)
        share_kmap = self._build_kshare_map()

        self.send({'dest': wsn.BROADCAST_ADDR,
                   'type': 'HEART_BEAT',
                   'source': self.ch_addr if self.ch_addr is not None else self.addr,
                   'gui': self.id,
                   'role': self.role,
                   'addr': self.addr,
                   'ch_addr': self.ch_addr,
                   'hop_count': self.hop_count,
                   'nbrs': my_neighbors,
                   'nbrs_k': share_kmap,
                   'created_at': self.now})  # <— NEW
        try:
            self._dbg(f"PKT_CREATE type=HEART_BEAT created_at={self.now:.3f}")
        except Exception:
            pass

    ###################
    def _build_kshare_map(self):
        """KG- Build K-1 hop share map (receiver adds +1)."""
        try:
            share_kmap = {}
            # 1) ensure 1-hop entries exist, cache in k_hop_next
            for gui, hb in (self.neighbors_table or {}).items():
                nh = hb.get('addr') if isinstance(hb, dict) else None
                if nh is not None:
                    share_kmap[gui] = 1
                    cur = self.k_hop_next.get(gui)
                    if cur is None or cur.get('hop', 10**9) > 1:
                        self.k_hop_next[gui] = {'next_hop': nh, 'hop': 1}
            # 2) include current K-hop knowledge up to K-1
            for tgt, rec in list(self.k_hop_next.items()):
                try:
                    h = int(rec.get('hop', 999999))
                except Exception:
                    h = 999999
                if h <= max(1, self.k_max - 1):
                    prev = share_kmap.get(tgt)
                    share_kmap[tgt] = h if prev is None else min(prev, h)
            return share_kmap
        except Exception:
            return {}

    ###################
    def send_join_request(self, dest):
        """Sending join request message to given destination address to join destination network

        Args:
            dest (Addr): Address of destination node
        Returns:

        """
        try:
            self._dbg(f"PKT_CREATE type=JOIN_REQUEST created_at={self.now:.3f}")
        except Exception:
            pass
        self.send({'dest': dest, 'type': 'JOIN_REQUEST', 'gui': self.id, 'created_at': self.now})

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
        try:
            self._dbg(f"PKT_CREATE type=JOIN_REPLY created_at={self.now:.3f}")
        except Exception:
            pass
        self.send({'dest': wsn.BROADCAST_ADDR, 'type': 'JOIN_REPLY', 'source': self.ch_addr,
                   'gui': self.id, 'dest_gui': gui, 'addr': addr, 'root_addr': self.root_addr,
                   'hop_count': self.hop_count+1, 'created_at': self.now})

    ###################
    def send_join_ack(self, dest):
        """Sending join acknowledgement message to given destination address.

        Args:
            dest (Addr): Address of destination node
        Returns:

        """
        try:
            self._dbg(f"PKT_CREATE type=JOIN_ACK created_at={self.now:.3f}")
        except Exception:
            pass
        self.send({'dest': dest, 'type': 'JOIN_ACK', 'source': self.addr,
                   'gui': self.id, 'created_at': self.now})

    ###################
    def route_and_forward_package(self, pck):
        """Routing and forwarding given package

        Args:
            pck (Dict): package to route and forward it should contain dest, source and type.
        Returns:

        """
        dest = pck['dest']
        path_type = None
        # clear previous decision-specific metadata
        pck.pop('_mesh_hop', None)

        # 1) Mesh-first: try to deliver using local/multihop knowledge
        # 1a) direct neighbor check via neighbors_table
        try:
            for entry in self.neighbors_table.values():
                if entry.get('addr') == dest or entry.get('ch_addr') == dest:
                    pck['next_hop'] = dest
                    path_type = 'DIRECT'
                    self._dbg(f"ROUTE DIRECT type={pck.get('type')} src={_addr_str(pck.get('source'))} dest={_addr_str(dest)} next={_addr_str(pck['next_hop'])}")
                    log_packet_route(pck, self, pck['next_hop'], path_type)
                    self._prepare_and_send(pck)
                    return
        except Exception:
            pass

        # 1b) K-hop knowledge via DV map: find GUI for dest, then use k_hop_next
        try:
            dest_gui = None
            for n in self.sim.nodes:
                if (getattr(n, 'addr', None) is not None and n.addr == dest) or \
                   (getattr(n, 'ch_addr', None) is not None and n.ch_addr == dest):
                    dest_gui = n.id
                    break
            if dest_gui is not None:
                rec = self.k_hop_next.get(dest_gui)
                if rec and rec.get('next_hop') is not None:
                    pck['next_hop'] = rec['next_hop']
                    path_type = 'MESH'
                    try:
                        pck['_mesh_hop'] = int(rec.get('hop'))
                    except Exception:
                        pck['_mesh_hop'] = ''
                    self._dbg(f"ROUTE MESH type={pck.get('type')} src={_addr_str(pck.get('source'))} dest={_addr_str(dest)} next={_addr_str(pck['next_hop'])} hop={rec.get('hop')}")
                    log_packet_route(pck, self, pck['next_hop'], path_type)
                    self._prepare_and_send(pck)
                    return
        except Exception:
            pass

        # 2) Tree fallback
        if self.role != Roles.ROOT:
            # default up to parent
            try:
                pck['next_hop'] = self.neighbors_table[self.parent_gui]['ch_addr']
                path_type = 'TREE_PARENT'
            except Exception:
                 pck['next_hop'] = None
        if self.ch_addr is not None:
            if dest.net_addr == self.ch_addr.net_addr:
                pck['next_hop'] = dest
                path_type = 'TREE_SAME_NET'
            else:
                for child_gui, child_networks in self.child_networks_table.items():
                    if dest.net_addr in child_networks:
                        try:
                            pck['next_hop'] = self.neighbors_table[child_gui]['addr']
                            path_type = 'TREE_CHILD'
                        except Exception:
                            pass
                        break

        self._dbg(f"ROUTE {path_type or 'TREE'} type={pck.get('type')} src={_addr_str(pck.get('source'))} dest={_addr_str(dest)} next={_addr_str(pck.get('next_hop'))}")
        log_packet_route(pck, self, pck.get('next_hop'), path_type or 'TREE')
 
        self._prepare_and_send(pck)

    ###################
    def send_network_request(self):
        """Sending network request message to root address to be cluster head

        Args:

        Returns:

        """
        self.route_and_forward_package({'dest': self.root_addr, 'type': 'NETWORK_REQUEST', 'source': self.addr, 'created_at': self.now})

    ###################
    def send_network_reply(self, dest, addr):
        """Sending network reply message to dest address to be cluster head with a new adress

        Args:
            dest (Addr): destination address
            addr (Addr): cluster head address of new network

        Returns:

        """
        self.route_and_forward_package({'dest': dest, 'type': 'NETWORK_REPLY', 'source': self.addr, 'addr': addr, 'created_at': self.now})

    ###################
    def send_network_update(self):
        """Sending network update message to parent

        Args:

        Returns:

        """
        child_networks = [self.ch_addr.net_addr]
        for networks in self.child_networks_table.values():
            child_networks.extend(networks)

        self.send({'dest': self.neighbors_table[self.parent_gui]['ch_addr'], 'type': 'NETWORK_UPDATE', 'source': self.addr,
                   'gui': self.id, 'child_networks': child_networks, 'created_at': self.now})

    ###################
    def on_receive(self, pck):
        """Executes when a package received.

        Args:
            pck (Dict): received package
        Returns:

        """
        # latency logging: if I am the destination of a directed packet, log delivery delay
        try:
            if pck.get('dest') not in (None, wsn.BROADCAST_ADDR):
                if pck['dest'] == self.addr or pck['dest'] == self.ch_addr:
                    log_packet_delivery(pck, self)
        except Exception:
            pass

        if self.role == Roles.ROOT or self.role == Roles.CLUSTER_HEAD:  # if the node is root or cluster head
            if 'next_hop' in pck.keys() and pck['dest'] != self.addr and pck['dest'] != self.ch_addr:  # forwards message if destination is not itself
                self.route_and_forward_package(pck)
                return
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
            if pck['type'] == 'PROBE':  # it waits and sends heart beat message once received probe message
                # yield self.timeout(.5)
                self.send_heart_beat()
            if pck['type'] == 'JOIN_REQUEST':  # it waits and sends join reply message once received join request
                # yield self.timeout(.5)
                self.send_join_reply(pck['gui'], wsn.Addr(self.ch_addr.net_addr, pck['gui']))
            if pck['type'] == 'NETWORK_REQUEST':  # it sends a network reply to requested node
                # yield self.timeout(.5)
                if self.role == Roles.ROOT:
                    new_addr = wsn.Addr(pck['source'].node_addr,254)
                    self.send_network_reply(pck['source'],new_addr)
            if pck['type'] == 'JOIN_ACK':
                self.members_table.append(pck['gui'])
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
            if pck['type'] == 'PROBE':
                # yield self.timeout(.5)
                self.send_heart_beat()
            if pck['type'] == 'JOIN_REQUEST':  # it sends a network request to the root
                self.received_JR_guis.append(pck['gui'])
                # yield self.timeout(.5)
                self.send_network_request()
            if pck['type'] == 'NETWORK_REPLY':  # it becomes cluster head and send join reply to the candidates
                self.set_role(Roles.CLUSTER_HEAD)
                try:
                    write_clusterhead_distances_csv("clusterhead_distances.csv")
                except Exception as e:
                    self.log(f"CH CSV export error: {e}")
                self.scene.nodecolor(self.id, 0, 0, 1)
                self.ch_addr = pck['addr']
                self.send_network_update()
                # yield self.timeout(.5)
                self.send_heart_beat()
                for gui in self.received_JR_guis:
                    # yield self.timeout(random.uniform(.1,.5))
                    self.send_join_reply(gui, wsn.Addr(self.ch_addr.net_addr,gui))

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
                    # log broadcast-to-me arrival delay (JOIN_REPLY)
                    log_packet_delivery(pck, self)
                    self.addr = pck['addr']
                    self.parent_gui = pck['gui']
                    self.root_addr = pck['root_addr']
                    self.hop_count = pck['hop_count']
                    self.draw_parent()
                    # join completion time
                    try:
                        if getattr(self, '_join_started_at', None) is not None and getattr(self, '_join_completed_at', None) is None:
                            self._join_completed_at = self.now
                            write_join_time(self)
                            try:
                                delay = self._join_completed_at - self._join_started_at
                                self._dbg(f"JOIN_TIME started={self._join_started_at:.3f} completed={self._join_completed_at:.3f} delay={delay:.3f}")
                            except Exception:
                                pass
                    except Exception:
                        pass
                    self.kill_timer('TIMER_JOIN_REQUEST')
                    self.send_heart_beat()
                    self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                    self.send_join_ack(pck['source'])
                    if self.ch_addr is not None: # it could be a cluster head which lost its parent
                        self.set_role(Roles.CLUSTER_HEAD)
                        self.send_network_update()
                    else:
                        self.set_role(Roles.REGISTERED)
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
                    self.addr = wsn.Addr(self.id, 254)
                    self.ch_addr = wsn.Addr(self.id, 254)
                    self.root_addr = self.addr
                    self.hop_count = 0
                    self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
                else:  # otherwise it keeps trying to sending probe after a long time
                    self.c_probe = 0
                    self.set_timer('TIMER_PROBE', 30)

        elif name == 'TIMER_HEART_BEAT':  # it sends heart beat message once heart beat timer fired
            self.send_heart_beat()
            self.set_timer('TIMER_HEART_BEAT', config.HEARTH_BEAT_TIME_INTERVAL)
            #print(self.id)
 
        elif name == 'TIMER_TX_SEND':
            self._tx_drain_due()

        elif name == 'TIMER_JOIN_REQUEST':  # if it has not received heart beat messages before, it sets timer again and wait heart beat messages once join request timer fired.
            if len(self.candidate_parents_table) == 0:
                self.become_unregistered()
            else:  # otherwise it chose one of them and sends join request
                self.select_and_join()

        elif name == 'TIMER_SENSOR':
            self.route_and_forward_package({'dest': self.root_addr, 'type': 'SENSOR', 'source': self.addr, 'sensor_value': random.uniform(10,50), 'created_at': self.now})
            timer_duration =  self.id % 20
            if timer_duration == 0: timer_duration = 1
            self.set_timer('TIMER_SENSOR', timer_duration)
        elif name == 'TIMER_EXPORT_CH_CSV':
            # Only root should drive exports (cheap guard)
            if self.role == Roles.ROOT:
                write_clusterhead_distances_csv("clusterhead_distances.csv")
                # reschedule
                self.set_timer('TIMER_EXPORT_CH_CSV', config.EXPORT_CH_CSV_INTERVAL)
        elif name == 'TIMER_EXPORT_NEIGHBOR_CSV':
            if self.role == Roles.ROOT:
                write_neighbor_distances_csv("neighbor_distances.csv")
                write_multihop_neighbors_csv("multihop_neighbors.csv")
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

# Routing CSV logger
ROUTE_CSV_PATH = getattr(config, 'ROUTE_CSV_PATH', 'packet_routes.csv')
ROUTE_STATS = Counter()

def log_packet_route(pck, current_node, next_hop, path_type):
    try:
        need_header = not os.path.exists(ROUTE_CSV_PATH) or os.path.getsize(ROUTE_CSV_PATH) == 0
        with open(ROUTE_CSV_PATH, 'a', newline='') as f:
            w = csv.writer(f)
            if need_header:
                w.writerow([
                    "time", "packet_type",
                    "source", "src_gui",
                    "current_node", "role",
                    "next_hop", "next_hop_gui",
                    "dest", "dest_gui",
                    "hop_to_root", "ttl",
                    "neighbor_count", "kmap_size", "members_count",
                    "trace_len", "mesh_hop",
                    "path_type"
                ])
            now = getattr(current_node, 'now', '')
            ptype = pck.get('type', '')
            src = _addr_str(pck.get('source'))
            dest = _addr_str(pck.get('dest'))
            # helpers to resolve GUI ids from addresses
            def _gui_for_addr(addr):
                if addr is None:
                    return ''
                try:
                    for n in current_node.sim.nodes:
                        if (getattr(n, 'addr', None) is not None and n.addr == addr) or \
                           (getattr(n, 'ch_addr', None) is not None and n.ch_addr == addr):
                            return n.id
                except Exception:
                    return ''
                return ''

            row = []
            row.append(f"{now:.5f}" if isinstance(now, (int, float)) else now)
            row.append(ptype)
            row.append(src)
            row.append(_gui_for_addr(pck.get('source')))
            row.append(current_node.id)
            row.append(_role_name(getattr(current_node, 'role', '')))
            row.append(_addr_str(next_hop))
            row.append(_gui_for_addr(next_hop))
            row.append(dest)
            row.append(_gui_for_addr(pck.get('dest')))
            row.append(getattr(current_node, 'hop_count', ''))
            row.append(pck.get('ttl', ''))
            row.append(len(getattr(current_node, 'neighbors_table', {}) or {}))
            row.append(len(getattr(current_node, 'k_hop_next', {}) or {}))
            row.append(len(getattr(current_node, 'members_table', []) or []))
            row.append(len(pck.get('route_gui', []) or []))
            row.append(pck.get('_mesh_hop', ''))
            row.append(path_type)
            w.writerow(row)
            # update simple in-memory stats for the run
            try:
                ROUTE_STATS['rows'] += 1
                ROUTE_STATS[f"type:{ptype}"] += 1
                ROUTE_STATS[f"path:{path_type}"] += 1
            except Exception:
                pass
    except Exception:
        pass


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

###########################################################
def write_multihop_neighbors_csv(path="multihop_neighbors.csv"):
    """Export 1..K-hop neighbor knowledge using k_hop_next."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "target_gui", "hop", "next_hop_addr", "geometric_distance"])
        for node in sim.nodes:
            if not hasattr(node, 'k_hop_next'):
                continue
            x1, y1 = NODE_POS.get(node.id, (None, None))
            if x1 is None:
                continue
            for tgt, rec in node.k_hop_next.items():
                x2, y2 = NODE_POS.get(tgt, (None, None))
                if x2 is None:
                    continue
                try:
                    dist = math.hypot(x1 - x2, y1 - y2)
                except Exception:
                    dist = None
                w.writerow([
                    node.id,
                    tgt,
                    rec.get('hop', ''),
                    _addr_str(rec.get('next_hop')),
                    f"{dist:.6f}" if dist is not None else ''
                ])


def log_packet_delivery(pck, receiver_node, path="packet_delays.csv"):
    """Log end-to-end delivery delay for directed or broadcast-to-specific-GUI packets."""
    try:
        created = pck.get('created_at', None)
        delivered = getattr(receiver_node, 'now', None)
        delay = ''
        if isinstance(created, (int, float)) and isinstance(delivered, (int, float)):
            delay = f"{delivered - created:.6f}"

        # Resolve an effective destination:
        # - If broadcast JOIN_REPLY has dest_gui == me, treat my addr as effective destination.
        effective_dest = pck.get('dest')
        if (effective_dest == wsn.BROADCAST_ADDR) and (pck.get('dest_gui') == receiver_node.id):
            effective_dest = receiver_node.addr or receiver_node.ch_addr

        # Helpers to resolve GUI from an Addr
        def _gui_for_addr(addr):
            if addr is None:
                return ''
            for n in receiver_node.sim.nodes:
                if (getattr(n, 'addr', None) == addr) or (getattr(n, 'ch_addr', None) == addr):
                    return n.id
            return ''

        with open(path, 'a', newline='') as f:
            w = csv.writer(f)
            if f.tell() == 0:
                w.writerow(["ptype", "src", "src_gui", "dest", "dest_gui", "created_at", "delivered_at", "delay"])
            w.writerow([
                pck.get('type', ''),
                _addr_str(pck.get('source')),
                _gui_for_addr(pck.get('source')),
                _addr_str(effective_dest),
                _gui_for_addr(effective_dest),
                f"{created:.6f}" if isinstance(created, (int, float)) else created,
                f"{delivered:.6f}" if isinstance(delivered, (int, float)) else delivered,
                delay,
            ])
        # optional debug line
        try:
            if getattr(receiver_node, 'debug_enabled', False):
                with open(getattr(receiver_node, 'debug_log_path', 'wsn_debug.log'), 'a') as df:
                    df.write(f"[{receiver_node.now:10.5f}] N{receiver_node.id} DELIVER_DELAY type={pck.get('type')} src={_addr_str(pck.get('source'))} dest={_addr_str(effective_dest)} delay={delay or ''}\n")
        except Exception:
            pass
    except Exception:
        pass


def write_join_time(node, path="join_times.csv"):
    """Append this node's join duration and update ROUTE_STATS for averaging."""
    try:
        started = getattr(node, '_join_started_at', None)
        completed = getattr(node, '_join_completed_at', None)
        if not isinstance(started, (int, float)) or not isinstance(completed, (int, float)):
            return
        delay = completed - started
        with open(path, 'a', newline='') as f:
            w = csv.writer(f)
            if f.tell() == 0:
                w.writerow(["node_id", "started_at", "completed_at", "join_delay"])
            w.writerow([node.id, f"{started:.6f}", f"{completed:.6f}", f"{delay:.6f}"])
        # aggregate
        ROUTE_STATS['join_count'] += 1
        ROUTE_STATS['join_total'] = ROUTE_STATS.get('join_total', 0.0) + delay
    except Exception:
        pass


def write_topology_csv(path="topology.csv"):
    """Easy-to-read final topology snapshot for grading/inspection."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "node_id", "role", "addr", "ch_addr", "parent_gui",
            "hop_count", "net_id", "neighbors", "members", "child_networks"
        ])
        for n in sim.nodes:
            role = getattr(n, "role", None)
            role_name = role.name if hasattr(role, "name") else str(role)
            addr = _addr_str(getattr(n, "addr", None))
            ch = _addr_str(getattr(n, "ch_addr", None))
            parent = getattr(n, "parent_gui", "")
            hop = getattr(n, "hop_count", "")
            net_id = getattr(getattr(n, "ch_addr", None), "net_addr", "")
            neigh_cnt = len(getattr(n, "neighbors_table", {}) or {})
            mem_cnt = len(getattr(n, "members_table", []) or [])
            child_cnt = len(getattr(n, "child_networks_table", {}) or {})
            w.writerow([n.id, role_name, addr, ch, parent, hop, net_id, neigh_cnt, mem_cnt, child_cnt])


def write_run_summary(path="run_summary.csv"):
    """Small, uniform summary + fingerprint to compare runs/assignments."""
    direct = ROUTE_STATS.get("path:DIRECT", 0)
    mesh = ROUTE_STATS.get("path:MESH", 0)
    tree_parent = ROUTE_STATS.get("path:TREE_PARENT", 0)
    tree_same = ROUTE_STATS.get("path:TREE_SAME_NET", 0)
    tree_child = ROUTE_STATS.get("path:TREE_CHILD", 0)
    tree_total = tree_parent + tree_same + tree_child
    rows = ROUTE_STATS.get("rows", 0)
    seed = getattr(config, "SEED", "")
    nodes = getattr(config, "SIM_NODE_COUNT", "")
    fp_src = f"seed={seed}|nodes={nodes}|rows={rows}|direct={direct}|mesh={mesh}|tree={tree_total}"
    fp = hashlib.sha1(fp_src.encode("utf-8")).hexdigest()[:12]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["nodes", nodes])
        w.writerow(["rows_logged", rows])
        w.writerow(["direct", direct])
        w.writerow(["mesh", mesh])
        w.writerow(["tree_parent", tree_parent])
        w.writerow(["tree_same_net", tree_same])
        w.writerow(["tree_child", tree_child])
        w.writerow(["tree_total", tree_total])
        # average join
        jn = ROUTE_STATS.get('join_count', 0)
        jt = ROUTE_STATS.get('join_total', 0.0)
        avg_join = (jt / jn) if jn > 0 else 0.0
        w.writerow(["join_count", jn])
        w.writerow(["avg_join_time", f"{avg_join:.6f}"])
        w.writerow(["fingerprint", fp])
    print(f"[summary] routes rows={rows} direct={direct} mesh={mesh} tree={tree_total} joins={jn} avg_join={avg_join:.4f} fp={fp}")


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
write_topology_csv("topology.csv")
write_run_summary("run_summary.csv")
print("Simulation Finished")


# Created 100 nodes at random locations with random arrival times.
# When nodes are created they appear in white
# Activated nodes becomes red
# Discovered nodes will be yellow
# Registered nodes will be green.
# Root node will be black.
# Routers/Cluster Heads should be blue
