Implementation Details
=======================

This document describes the implementation details of the WSN protocol simulation, including code structure, key classes, and important functions.

Code Structure
--------------

The project is organized as follows:

::

   EE662Fall2025_update1/
   ├── wsnlab/
   │   ├── data_collection_tree.py    # Main protocol implementation
   │   └── source/
   │       ├── config.py              # Configuration parameters
   │       ├── wsnlab.py              # Base simulation engine
   │       └── wsnlab_vis.py          # Visualization layer
   ├── generate_all_plots.py          # Plotting and analysis
   ├── run_batch_simulations.py       # Batch simulation runner
   └── docs/                          # Sphinx documentation

Core Classes
------------

SensorNode Class
~~~~~~~~~~~~~~~~

The main node class implementing the protocol is ``SensorNode`` in ``wsnlab/data_collection_tree.py``.

Key Attributes
^^^^^^^^^^^^^^

`The SensorNode class initializes with the following attributes in ``init()``:

.. code-block:: python

   class SensorNode(wsn.Node):
       # Network addressing
       addr: Addr                      # Network address [cluster_id, node_id]
       ch_addr: Addr                   # Cluster head address
       parent_gui: int                 # GUI ID of parent node
       root_addr: Addr                 # Address of ROOT node
       
       # Role and state
       role: Roles                     # Current role (UNDISCOVERED, UNREGISTERED, etc.)
       is_root_eligible: bool          # True if node can become ROOT
       is_shutdown: bool               # True if node shut down due to low energy
       is_failed: bool                 # True if node has failed
       
       # Discovery and neighbors
       neighbors_table: dict            # One-hop neighbor information
       multihop_neighbor_table: dict    # Multi-hop neighbor information
       candidate_parents_table: list   # List of candidate parent GUI IDs
       c_probe: int                     # Probe message counter
       th_probe: int                    # Probe threshold (default: 10)
       hop_count: int                   # Hop count to ROOT
       
       # Cluster management
       members_table: list             # List of child member addresses
       child_networks_table: dict       # Child network information
       node_addr_pool: dict             # Available node addresses in cluster
       cluster_addr_pool: dict         # Available cluster IDs (ROOT only)
       received_JR_guis: list          # GUI IDs that sent JOIN_REQUEST
       
       # Energy management
       energy_remaining: float         # Remaining battery energy (Joules)
       energy_initial: float           # Initial battery energy
       energy_tx_total: float          # Total TX energy consumed
       energy_rx_total: float          # Total RX energy consumed
       energy_baseline_total: float    # Total baseline energy consumed
       tx_power_dbm: float             # Current TX power level (dBm)
       cluster_tx_power_dbm: float     # Cluster TX power (if in cluster)
       
       # Cluster head transfer
       ch_transfer_enabled: bool       # Enable CH transfer
       ch_transfer_in_progress: bool   # Transfer in progress flag
       ch_transfer_candidate: int      # Candidate GUI for transfer
       
       # Timing and cooldowns
       wake_up_time: float             # Time when node woke up
       registered_time: float          # Time when node registered
       registered_since: float          # Time since registration
       failed_join_attempts: int       # Number of failed join attempts
       join_reply_last_sent: dict      # Last JOIN_REPLY sent time per GUI
       join_reply_cooldown: float       # JOIN_REPLY cooldown (5.0s)
       last_join_request_sent_time: float  # Last JOIN_REQUEST time
       join_request_cooldown: float    # JOIN_REQUEST cooldown (20s)
       last_trigger_ch_creation_time: float  # Last TRIGGER_CH_CREATION time
       trigger_ch_creation_cooldown: float   # TRIGGER_CH_CREATION cooldown (60s)
       
       # Failure and recovery
       failure_time: float             # Time when node failed
       role_before_failure: Roles       # Role before failure
       children_before_failure: list    # Children before failure

Key Methods
^^^^^^^^^^^

Initialization and Setup
'''''''''''''''''''''''''

* ``init()``: Initializes node with default values and sets role to UNDISCOVERED
* ``run()``: Sets arrival timer to wake up node
* ``set_role(new_role, recolor=True, reason="")``: Changes node role and updates visual color
* ``debug_log(enabled, message)``: Logs debug message if enabled

Neighbor Discovery
'''''''''''''''''''

* ``update_neighbor(pck)``: Updates neighbor table from HEART_BEAT message
  * Calculates Euclidean distance
  * Updates candidate parents table
  * Adds to multihop_neighbor_table if enabled
  * Cleans stale neighbors periodically

* ``process_neighbor_share(pck)``: Processes NEIGHBOR_SHARE packet for multi-hop discovery
  * Updates multihop_neighbor_table with hop distance
  * Respects MAX_HOP_DISTANCE limit

* ``share_neighbor_info()``: Broadcasts neighbor table information
  * Sends NEIGHBOR_SHARE packet with neighbors_info
  * Only active if ENABLE_MULTIHOP_DISCOVERY is True

* ``_cleanup_stale_neighbors()``: Removes neighbors not seen for 3×HEART_BEAT_INTERVAL

Cluster Management
'''''''''''''''''''

* ``_init_address_pool()``: Initializes node address pool (1 to MAX_CHILD_NODES_ALLOWED_PER_CLUSTER)
* ``_assign_child_address(child_gui)``: Assigns next available address to child node
* ``select_and_join()``: Selects best candidate parent and sends JOIN_REQUEST
* ``send_join_request(dest)``: Sends JOIN_REQUEST to destination
* ``send_join_reply(gui, addr)``: Sends JOIN_REPLY with assigned address
* ``send_join_ack(dest)``: Sends JOIN_ACK acknowledgment
* ``send_network_request()``: Sends NETWORK_REQUEST to ROOT for cluster ID
* ``send_network_reply(dest, addr)``: ROOT sends NETWORK_REPLY with cluster ID
* ``send_network_update()``: Sends NETWORK_UPDATE to parent about child networks
* ``initiate_ch_transfer()``: Initiates cluster head role transfer to farthest member
* ``find_farthest_member()``: Finds member with maximum distance for CH transfer
* ``_trigger_ch_creation()``: Broadcasts TRIGGER_CH_CREATION to trigger nearby CH creation
* ``become_router(reason)``: Converts CH to ROUTER role
* ``become_unregistered()``: Resets node to UNREGISTERED state

Routing
'''''''

* ``route_and_forward_package(pck)``: Main routing function implementing mesh-first, tree-fallback
* ``_record_route(pck, path_label, next_hop)``: Records routing decision to packet_routes.csv
* ``_get_parent_next_hop()``: Gets parent address for tree routing

Energy Management
''''''''''''''''''

* ``check_energy_level()``: Checks if energy is below BATTERY_ENERGY_MIN threshold
* ``shutdown_node(reason)``: Shuts down node due to low energy, changes color to gray
* ``update_cluster_tx_power()``: Updates TX power based on cluster or orphan status
  * Uses cluster TX power if in cluster
  * Applies orphan boost if ADAPTIVE_TX_POWER_FOR_ORPHANS enabled

Recovery
''''''''

* ``fail_node()``: Simulates node failure, marks children as orphans
* ``recover_node()``: Simulates node recovery, resets to UNDISCOVERED state
* ``become_orphan(reason)``: Marks node as orphaned, becomes UNREGISTERED

Packet Transmission
'''''''''''''''''''

* ``send(pck)``: Overrides base send() to add energy deduction and packet loss
* ``send_probe()``: Sends PROBE broadcast message
* ``send_heart_beat()``: Sends HEART_BEAT broadcast with node information
* ``send_random_data_packet()``: Sends SENSOR_DATA packet to ROOT

Helper Methods
''''''''''''''

* ``_find_node_by_addr(addr)``: Finds node object by network address
* ``_find_node_by_gui(gui)``: Finds node object by GUI ID
* ``_check_existing_ch_in_cluster(cluster_id)``: Checks if CH already exists for cluster

Simulator Class
~~~~~~~~~~~~~~~

The base simulator class is in ``wsnlab/source/wsnlab.py``:

* **Simulator**: Manages simulation environment using SimPy
* **Node**: Base node class with basic operations
* **Addr**: Network address class with net_addr and node_addr

Visualization Class
~~~~~~~~~~~~~~~~~~~

The visualization layer is in ``wsnlab/source/wsnlab_vis.py``:

* **Node**: Visualization wrapper for base Node class
  * Adds scene drawing capabilities
  * Manages node colors based on role
  * Handles packet visualization if enabled

* **Simulator**: Wraps base simulator with Tkinter visualization
  * Creates Tkinter window for visualization
  * Manages simulation time and updates
  * Handles window events and updates

* **Scene**: Manages visual elements in Tkinter canvas
  * Node circles with colors
  * Links between nodes
  * TX range circles
  * Packet trace visualization (if ENABLE_PACKET_VISUALIZATION is True)

Key Functions
-------------

Energy Calculation Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These functions calculate energy consumption based on CC2420 specifications:

``calculate_tx_energy(packet_size_bytes, tx_power_dbm, include_pll_overhead)``
   Calculates transmission energy for a packet.

   Parameters:
   * ``packet_size_bytes``: Packet payload size in bytes
   * ``tx_power_dbm``: TX power in dBm (-25 to 0)
   * ``include_pll_overhead``: Whether to include PLL overhead

   Returns:
   * Energy in Joules

``calculate_rx_energy(packet_size_bytes, include_pll_overhead)``
   Calculates reception energy for a packet.

   Parameters:
   * ``packet_size_bytes``: Packet payload size in bytes
   * ``include_pll_overhead``: Whether to include PLL overhead

   Returns:
   * Energy in Joules

``calculate_transmission_time(packet_size_bytes)``
   Calculates transmission time for a packet.

   Returns:
   * Transmission time in seconds

``calculate_reception_time(packet_size_bytes)``
   Calculates reception time for a packet.

   Returns:
   * Reception time in seconds

``estimate_packet_size(packet)``
   Estimates packet size based on packet type.

   Returns:
   * Estimated packet size in bytes

Logging Functions
~~~~~~~~~~~~~~~~~

``log_packet_delivery(pck, receiver_node)``
   Records end-to-end delay when packet reaches destination.

   Logs:
   * Base delay (simulation time difference)
   * Total delay (including TX/RX/processing time)
   * Transmission time
   * Reception time
   * Processing time
   * Number of hops

``record_packet_path(pck, receiver_node)``
   Records complete path for SENSOR_DATA packets.

   Logs:
   * Packet ID
   * Source and destination
   * Complete path (node IDs)
   * Hop count
   * Delay

``log_registration_time(node_id, wake_time, registered_time)``
   Logs node join time.

``log_role_change(node_id, old_role, new_role, time, reason)``
   Logs role change events.

``log_recovery_event(node_id, failure_time, recovery_time, orphan_count, role_before, role_after)``
   Logs node recovery events.

``log_orphan_event(node_id, time, reason, parent_id)``
   Logs orphan node events.

Routing Logic
-------------

The routing function ``route_and_forward_package()`` implements the mesh-first, tree-fallback strategy. The function performs the following steps:

Pre-Routing Checks
~~~~~~~~~~~~~~~~~~~

1. **Destination Check**: Returns if destination is None
2. **Broadcast Check**: Returns if destination is BROADCAST_ADDR
3. **Route Trace**: Adds current node ID to route_trace list
4. **Loop Detection**: Drops packet if node visited more than once
5. **Hop Limit**: Drops packet if route_trace length > 20 hops
6. **Self Check**: Returns if destination matches node's own address

Mesh Routing (if ENABLE_MESH_ROUTING is True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Step 1: Direct Neighbor Check
   Checks neighbors_table for destination address (both addr and ch_addr fields):
   
   .. code-block:: python
   
      neighbor_match = next(
          (entry for entry in self.neighbors_table.values()
           if addr_equals(entry.get('addr'), dest) or 
              addr_equals(entry.get('ch_addr'), dest)),
          None
      )
   
   If found:
   * Route label: "DIRECT" for one-hop, "MESH" for multi-hop
   * Sets next_hop to destination address
   * Forwards packet

Step 2: Multi-Hop Neighbor Check (if ENABLE_MULTIHOP_DISCOVERY is True)
   Checks multihop_neighbor_table for destination:

.. code-block:: python

   multihop_match = next(
       (info for gui, info in self.multihop_neighbor_table.items() 
        if addr_equals(info.get('addr'), dest)),
       None
   )
   
   If found:
   * Gets next_hop GUI from multihop_match
   * Looks up next_hop address in neighbors_table
   * Route label: "MESH_2H", "MESH_3H", etc. based on hop_dist
   * Forwards packet to next_hop

Tree Routing (if ENABLE_TREE_ROUTING is True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Step 3: Cluster Member Check
   If node is CLUSTER_HEAD or ROOT:

.. code-block:: python

       member_match = next(
           (entry for entry in self.members_table if entry == dest),
           None
       )
   
   If found:
   * Route label: "CLUSTER_MEMBER"
   * Sets next_hop to destination address
   * Routes directly to cluster member

Step 4: Same Cluster Check
   Checks if destination is in same cluster:

.. code-block:: python

      if self.ch_addr is not None and hasattr(dest, 'net_addr'):
          if dest.net_addr == self.ch_addr.net_addr:
              pck['next_hop'] = dest
              path_str = "TREE_SAME_CLUSTER"
   
   If true:
   * Route label: "TREE_SAME_CLUSTER"
   * Sets next_hop to destination address
   * Routes directly within cluster

Step 5: Child Network Check
   Checks child_networks_table:

.. code-block:: python

   for child_gui, child_networks in self.child_networks_table.items():
          if hasattr(dest, 'net_addr') and dest.net_addr in child_networks:
              child_info = self.neighbors_table.get(child_gui)
              if child_info:
                  pck['next_hop'] = child_info.get('addr')
                  path_str = "TREE_CHILD"
   
   If found:
   * Route label: "TREE_CHILD"
   * Routes to child cluster head address

Step 6: Parent Fallback
   Routes up tree to parent:

.. code-block:: python

   if self.role != Roles.ROOT and self.parent_gui is not None:
       parent_info = self.neighbors_table.get(self.parent_gui)
       if parent_info:
              pck['next_hop'] = parent_info.get('ch_addr') or parent_info.get('addr')
              path_str = "TREE_PARENT"
   
   Route label: "TREE_PARENT"
   Routes to parent node address (prefers ch_addr, falls back to addr)
   
   If no route found after all steps:
   * Route label: "NO_ROUTE"
   * Packet is dropped
   * Logs ROUTE_FAIL event

Timer System
------------

The protocol uses a timer-based event system:

Key Timers
~~~~~~~~~~

* ``TIMER_ARRIVAL``: Node wake-up time (set in run() method)
* ``TIMER_PROBE``: Probe message sending (interval: 1 second, max 10 attempts)
* ``TIMER_HEART_BEAT``: Periodic heartbeat transmission (interval: HEARTH_BEAT_TIME_INTERVAL, default 3s)
* ``TIMER_JOIN_REQUEST``: Join request sending (interval: 20 seconds, with cooldown)
* ``TIMER_NEIGHBOR_SHARE``: Neighbor table sharing (interval: NEIGHBOR_SHARE_INTERVAL, default 30s)
* ``TIMER_SENSOR``: Data packet generation (interval: DATA_PACKET_INTERVAL, default 10s)
* ``TIMER_BASELINE_ENERGY``: Baseline energy consumption (interval: 1.0 second)
* ``TIMER_CLUSTER_OPTIMIZATION``: Cluster optimization (interval: CLUSTER_OPTIMIZATION_INTERVAL, default 100s, ROOT only)
* ``TIMER_CH_TRANSFER_DELAY``: CH transfer delay (2 seconds after receiving JOIN_REPLY)
* ``TIMER_PROACTIVE_CH``: Proactive CH creation (interval: PROACTIVE_CH_TIMER, default 20s)
* ``TIMER_EXPORT_CH_CSV``: Export cluster head distances CSV (interval: EXPORT_CH_CSV_INTERVAL, default 10s, ROOT only)
* ``TIMER_EXPORT_NEIGHBOR_CSV``: Export neighbor distances CSV (interval: EXPORT_NEIGHBOR_CSV_INTERVAL, default 10s, ROOT only)
* ``TIMER_PERIODIC_SNAPSHOT``: Periodic network snapshot (if enabled)
* ``TIMER_NODE_FAILURE_{id}``: Scheduled node failure (from SCHEDULED_FAILURES)
* ``TIMER_NODE_RECOVERY_{id}``: Scheduled node recovery (from SCHEDULED_RECOVERIES)

Timer Handler
~~~~~~~~~~~~~

The ``on_timer_fired()`` method handles all timer events:

.. code-block:: python

   def on_timer_fired(self, name, *args, **kwargs):
       if name == 'TIMER_ARRIVAL':
           # Node wakes up
       elif name == 'TIMER_PROBE':
           # Send probe message
       elif name == 'TIMER_HEART_BEAT':
           # Send heartbeat
       # ... etc

Packet Processing
-----------------

The ``on_receive()`` method processes incoming packets based on node role and packet type. The method first deducts RX energy if energy model is enabled, then processes the packet.

Role-Based Processing
~~~~~~~~~~~~~~~~~~~~~

* **ROOT**: Processes JOIN_REQUEST, NETWORK_REQUEST, NETWORK_UPDATE, CH_TRANSFER_ACK
* **CLUSTER_HEAD**: Processes JOIN_REQUEST, NETWORK_UPDATE, CH_TRANSFER, CH_TRANSFER_ACK, TRIGGER_CH_CREATION
* **REGISTERED**: Processes HEART_BEAT, JOIN_REQUEST (can forward or become CH), TRIGGER_CH_CREATION, NETWORK_REPLY
* **UNREGISTERED**: Processes HEART_BEAT, JOIN_REPLY, TRIGGER_CH_CREATION
* **ROUTER**: Processes HEART_BEAT, forwards packets, maintains routing tables
* **UNDISCOVERED**: Processes HEART_BEAT (transitions to UNREGISTERED)

Packet Type Handling
~~~~~~~~~~~~~~~~~~~~

Each packet type has specific handling logic:

* **HEART_BEAT**: Updates neighbor table via update_neighbor(), updates candidate parents
* **JOIN_REQUEST**: 
  * CLUSTER_HEAD/ROOT: Assigns address if cluster not full, sends JOIN_REPLY
  * REGISTERED: Can forward to parent or become CH if isolated
* **JOIN_REPLY**: Accepts address, becomes REGISTERED, sends JOIN_ACK, sets up timers
* **JOIN_ACK**: CH adds member to members_table
* **NETWORK_REQUEST**: ROOT assigns cluster ID, sends NETWORK_REPLY
* **NETWORK_REPLY**: Node receives cluster ID, becomes CLUSTER_HEAD
* **NETWORK_UPDATE**: Parent updates child_networks_table
* **NEIGHBOR_SHARE**: Processes multi-hop neighbor information via process_neighbor_share()
* **SENSOR_DATA**: Routes to destination via route_and_forward_package(), records path when delivered
* **CH_TRANSFER**: Member accepts CH role, sends CH_TRANSFER_ACK
* **CH_TRANSFER_ACK**: Old CH becomes ROUTER
* **TRIGGER_CH_CREATION**: REGISTERED nodes can become CH to help UNREGISTERED nodes

Energy Deduction
----------------

Energy is deducted in three places:

Transmission
~~~~~~~~~~~~

In ``send()`` method before packet transmission:

.. code-block:: python

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
       else:
           self.energy_remaining = 0.0
           self.shutdown_node("Insufficient energy for transmission")

Reception
~~~~~~~~~

In ``on_receive()`` method when packet is received:

.. code-block:: python

   if config.ENABLE_ENERGY_MODEL and not self.is_shutdown:
       packet_size = estimate_packet_size(pck)
       rx_energy = calculate_rx_energy(packet_size, include_pll_overhead=True)
       if self.energy_remaining >= rx_energy:
       self.energy_remaining -= rx_energy
       self.energy_rx_total += rx_energy
       else:
           self.energy_remaining = 0.0
           self.shutdown_node("Insufficient energy for reception")

Baseline
~~~~~~~~

In ``TIMER_BASELINE_ENERGY`` handler (every 1.0 second):

.. code-block:: python

   if config.ENABLE_ENERGY_MODEL and not self.is_shutdown:
   baseline_power = config.CC2420_VOLTAGE * config.BASELINE_CURRENT
   baseline_energy = baseline_power * 1.0  # For 1 second
       if self.energy_remaining >= baseline_energy:
   self.energy_remaining -= baseline_energy
           self.energy_baseline_total += baseline_energy
           self.check_energy_level()
       else:
           self.energy_remaining = 0.0
           self.shutdown_node("Insufficient energy for baseline operation")

Configuration System
--------------------

All configuration is centralized in ``wsnlab/source/config.py``:

Parameter Categories
~~~~~~~~~~~~~~~~~~~~

* **Network Properties**: TX range, node count, terrain size
* **Cluster Formation**: Max children per cluster, cluster count
* **Protocol Parameters**: Heartbeat interval, neighbor share interval
* **Energy Model**: Battery capacity, TX power levels, baseline current
* **Recovery**: Failure rate, recovery time, number of failures
* **Optimization**: Optimization mode, interval

Access Pattern
~~~~~~~~~~~~~~

Configuration is accessed via:

.. code-block:: python

   import config
   max_children = config.MAX_CHILD_NODES_ALLOWED_PER_CLUSTER
   tx_range = config.NODE_TX_RANGE

Global State
------------

The simulation maintains several global data structures defined at module level:

* ``ALL_NODES``: List of all SensorNode objects
* ``CLUSTER_HEADS``: List of cluster head node objects
* ``NODE_POS``: Dictionary mapping node GUI ID to (x, y) position tuple
* ``CLUSTER_TX_POWER``: Dictionary mapping cluster ID (net_addr) to TX power in dBm
* ``FAILED_NODES``: Set of currently failed node GUI IDs
* ``ORPHANED_NODES``: Set of currently orphaned node GUI IDs
* ``ROLE_COUNTS``: Counter dictionary tracking count of nodes per role
* ``PACKET_STATS``: Dictionary tracking packet attempts and drops
* ``SCHEDULED_FAILURES``: List of scheduled node failure events
* ``SCHEDULED_RECOVERIES``: List of scheduled node recovery events
* ``RECOVERY_EVENTS``: List of recovery event records

These are used for coordination, analysis, and logging across the simulation. The global state is updated by individual nodes during protocol execution.

