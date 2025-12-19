Protocol Design
================

This document describes the detailed design of the WSN protocol, including neighbor discovery, cluster formation, routing mechanisms, and network recovery.

Network Architecture
--------------------

The protocol implements a **cluster-tree mesh ad-hoc network** where:

* Nodes are organized into clusters with cluster heads (CH)
* Cluster heads communicate with each other via router nodes
* The network forms a tree structure with the ROOT node at the top
* Mesh routing is used for local communication, tree routing for global

Node Roles
----------

The protocol defines six node roles (in order: UNDISCOVERED, UNREGISTERED, ROOT, REGISTERED, CLUSTER_HEAD, ROUTER):

UNDISCOVERED
~~~~~~~~~~~~

* Initial state when node wakes up
* Node is sleeping and cannot receive messages
* Sends periodic PROBE messages (every 1 second) to discover the network
* Transitions to UNREGISTERED when HEART_BEAT is received from any neighbor
* Maximum probe attempts: 10 (configurable via ``th_probe``)

UNREGISTERED
~~~~~~~~~~~~

* Node has discovered neighbors but hasn't joined a cluster
* Sends JOIN_REQUEST to candidate parents (CLUSTER_HEAD or ROOT)
* Maintains candidate parents table from neighbors
* Can trigger cluster head creation if no parent is available after failed attempts
* Trigger threshold: ``UNREGISTERED_CH_TRIGGER_THRESHOLD`` (default: 1 failed attempt)
* Can use adaptive TX power boost if isolated (``ADAPTIVE_TX_POWER_FOR_ORPHANS``)

REGISTERED
~~~~~~~~~~

* Node has joined a cluster and received an address
* Sends periodic HEART_BEAT messages (interval: ``HEARTH_BEAT_TIME_INTERVAL``, default: 3 seconds)
* Can proactively become a cluster head if:
  * ``ENABLE_PROACTIVE_CH_CREATION`` is True
  * After ``PROACTIVE_CH_TIMER`` seconds (default: 20 seconds)
  * No JOIN_REQUEST received
  * No parent assigned
  * Isolated (no cluster head address)

CLUSTER_HEAD
~~~~~~~~~~~~

* Manages a cluster of nodes
* Assigns addresses to child nodes (1 to ``MAX_CHILD_NODES_ALLOWED_PER_CLUSTER``)
* Maintains member table and child network information
* Can transfer CH role to reduce cluster overlap (if ``ENABLE_CH_TRANSFER`` is True)
* Minimum members for transfer: ``MIN_MEMBERS_FOR_TRANSFER`` (default: 1)
* Cannot transfer if node is ROOT
* Duplicate CH detection: If another CH exists with same cluster ID, becomes ROUTER instead

ROUTER
~~~~~~

* Bridges between cluster heads
* Does not have its own cluster
* Forwards packets between clusters
* Helps reduce cluster overlap
* Can be created from CH transfer or duplicate CH detection
* Can handle orphaned children when parent CH fails

ROOT
~~~~

* Special cluster head at the top of the tree
* Node ID: ``ROOT_ID`` (typically node 1)
* Coordinates cluster ID assignment via NETWORK_REQUEST/NETWORK_REPLY
* Runs cluster optimization protocols
* Cannot transfer CH role
* Does not go through normal registration process

Neighbor Discovery Protocol
---------------------------

One-Hop Discovery
~~~~~~~~~~~~~~~~~~

Nodes discover direct neighbors through HEART_BEAT messages:

1. **HEART_BEAT Transmission**: Nodes send periodic HEART_BEAT messages
2. **Neighbor Table Update**: Receiving nodes update their neighbor table with:
   - Neighbor's GUI ID
   - Neighbor's address (node address and/or cluster head address)
   - Neighbor's role
   - Distance (Euclidean)
   - Hop count to ROOT
   - Arrival time

3. **Candidate Parent Selection**: Nodes identify neighbors that can be parents:
   - Must be CLUSTER_HEAD or ROOT
   - Must have a valid address
   - REGISTERED and ROUTER nodes cannot accept children

Multi-Hop Discovery
~~~~~~~~~~~~~~~~~~~

For extended neighbor discovery:

1. **Neighbor Sharing**: Nodes periodically share their neighbor tables
2. **Distance Vector**: Uses distance-vector style updates
3. **Hop Distance Tracking**: Maintains hop distance to each known neighbor
4. **Next Hop Information**: Stores next hop for routing to multi-hop neighbors

The multi-hop neighbor table structure:

.. code-block:: python

   {
       neighbor_gui: {
           'hop_dist': int,      # Number of hops to neighbor
           'next_hop': int,      # GUI of next hop node
           'distance': float,    # Euclidean distance
           'addr': Addr          # Neighbor's address
       }
   }

Cluster Formation Protocol
--------------------------

Cluster Head Election
~~~~~~~~~~~~~~~~~~~~~~

Cluster heads are created through several mechanisms:

1. **ROOT Assignment**: ROOT assigns cluster IDs to nodes requesting to become CH
2. **Proactive Creation**: REGISTERED nodes can proactively become CH if:
   - No JOIN_REQUEST received after a timeout
   - Received PROBE from UNREGISTERED nodes
3. **Triggered Creation**: UNREGISTERED nodes can trigger nearby REGISTERED nodes to become CH

Address Assignment
~~~~~~~~~~~~~~~~~~

* **Cluster ID**: Assigned by ROOT from a pool of available cluster IDs
* **Node Address**: Assigned by cluster head from 1 to MAX_CHILD_NODES_ALLOWED_PER_CLUSTER
* **Address Format**: ``[cluster_id, node_id]``

Cluster Size Control
~~~~~~~~~~~~~~~~~~~~

* Each cluster head maintains an address pool
* Maximum children per cluster: ``MAX_CHILD_NODES_ALLOWED_PER_CLUSTER``
* When cluster is full, JOIN_REQUEST is rejected (no reply sent)
* Child nodes timeout and try other cluster heads

Cluster Head Transfer
~~~~~~~~~~~~~~~~~~~~~

To reduce cluster overlap (enabled via ``ENABLE_CH_TRANSFER``, default: True):

1. **Conditions**: CH can transfer if:
   * ``ENABLE_CH_TRANSFER`` is True
   * Not ROOT node
   * Has at least ``MIN_MEMBERS_FOR_TRANSFER`` members (default: 1)
   * Has valid cluster address (``ch_addr is not None``)
   * Transfer not already in progress

2. **Farthest Member Selection**: CH finds the farthest member from itself in neighbors_table
   * Uses Euclidean distance
   * Must have valid address and distance information

3. **Transfer Message**: Sends CH_TRANSFER message to selected member with:
   * Cluster address to transfer
   * Member address information

4. **Role Change**: 
   * Member accepts and becomes new CH
   * Old CH becomes ROUTER
   * New CH sends CH_TRANSFER_ACK to confirm

5. **Address Transfer**: New CH inherits the cluster address
   * Old CH removes new CH from members_table
   * Address pool is transferred
   * Orphaned children of old CH are handled

Routing Protocol
----------------

The routing protocol uses a **mesh-first, tree-fallback** strategy:

Mesh Routing
~~~~~~~~~~~~

Enabled via ``ENABLE_MESH_ROUTING`` (default: True). Steps:

1. **Direct Neighbor Check**: Check if destination address matches any entry in ``neighbors_table``
   * Checks both ``addr`` and ``ch_addr`` fields
   * If found, route directly to neighbor

2. **Multi-Hop Check**: Check if destination is in ``multihop_neighbor_table``
   * Uses stored ``next_hop`` information
   * Checks hop distance (must be <= ``MAX_HOP_DISTANCE``, default: 3)

3. **Next Hop Selection**: 
   * For multi-hop neighbors, use stored ``next_hop`` GUI ID
   * Look up next hop in ``neighbors_table``
   * Route label: "MESH" for multi-hop, "DIRECT" for one-hop

4. **Route Forwarding**: Forward packet to next hop with route trace updated

Tree Routing
~~~~~~~~~~~~

Enabled via ``ENABLE_TREE_ROUTING`` (default: True). Used when mesh routing fails or is disabled:

1. **Cluster Member Check**: If destination is in ``members_table``, route directly to member
   * Route label: "TREE_MEMBER"

2. **Same Cluster Check**: If destination has same cluster ID (``net_addr``), route to parent
   * Route label: "TREE_SAME_CLUSTER"

3. **Child Network Check**: If destination is in ``child_networks_table``, route to child CH
   * Route label: "TREE_CHILD_NETWORK"

4. **Parent Fallback**: Route up the tree to parent (``parent_gui``)
   * Route label: "TREE_PARENT"
   * If no parent, route fails

Loop Prevention
~~~~~~~~~~~~~~~

* **Route Tracing**: Each packet maintains a ``route_trace`` list
* **Visit Detection**: Nodes check if they're already in route_trace
* **Loop Dropping**: Packets visiting a node twice are dropped
* **Hop Limit**: Maximum 20 hops to prevent excessive routing

Packet Types
------------

The protocol uses several packet types:

Control Packets
~~~~~~~~~~~~~~~

* **PROBE**: Broadcast by UNDISCOVERED nodes to discover network
  * Sent every 1 second (TIMER_PROBE)
  * Maximum 10 attempts (``th_probe``)
  * Processing time: 0.0001 seconds

* **HEART_BEAT**: Periodic broadcast with node information
  * Interval: ``HEARTH_BEAT_TIME_INTERVAL`` (default: 3 seconds)
  * Contains: address, cluster head address, role, hop count to ROOT
  * Processing time: 0.0001 seconds
  * Updates neighbor tables

* **JOIN_REQUEST**: Request to join a cluster
  * Sent by UNREGISTERED nodes to candidate parents
  * Interval: 20 seconds (TIMER_JOIN_REQUEST)
  * Processing time: 0.0002 seconds

* **JOIN_REPLY**: Response with assigned address
  * Sent by CLUSTER_HEAD or ROOT in response to JOIN_REQUEST
  * Contains assigned address (cluster_id, node_id)
  * Processing time: 0.0002 seconds
  * Cooldown: 5 seconds per destination to prevent spam

* **JOIN_ACK**: Acknowledgment of successful join
  * Sent by node after receiving JOIN_REPLY
  * Processing time: 0.0001 seconds

* **NETWORK_REQUEST**: Request to become cluster head
  * Sent to ROOT to request cluster ID
  * Processing time: 0.0002 seconds
  * Requires valid address and root address known

* **NETWORK_REPLY**: Response with cluster ID assignment
  * Sent by ROOT in response to NETWORK_REQUEST
  * Contains assigned cluster address
  * Processing time: 0.0003 seconds

* **NETWORK_UPDATE**: Update parent about child networks
  * Sent by CH to parent to inform about child clusters
  * Processing time: 0.0003 seconds

* **NEIGHBOR_SHARE**: Share neighbor table information
  * Interval: ``NEIGHBOR_SHARE_INTERVAL`` (default: 30 seconds)
  * Enables multi-hop neighbor discovery
  * Processing time: 0.0002 seconds
  * Only shared if ``ENABLE_MULTIHOP_DISCOVERY`` is True

Data Packets
~~~~~~~~~~~~

* **SENSOR_DATA**: Data packets from sensor nodes to ROOT
  * Includes packet ID, source, destination, and route trace
  * Processing time: 0.0002 seconds
  * Interval: ``DATA_PACKET_INTERVAL`` (default: 10 seconds)
  * Full path recorded in ``packet_paths.csv``

Special Packets
~~~~~~~~~~~~~~~

* **CH_TRANSFER**: Transfer cluster head role to another node
  * Sent by CH to selected member
  * Contains cluster address to transfer
  * Member can accept or reject

* **CH_TRANSFER_ACK**: Acknowledgment of CH transfer
  * Sent by new CH to confirm role transfer
  * Old CH becomes ROUTER upon receiving ACK

* **TRIGGER_CH_CREATION**: Trigger nearby node to become CH
  * Broadcast by UNREGISTERED nodes after failed join attempts
  * Rate-limited with adaptive cooldown
  * REGISTERED nodes receiving this can become CH to help

Energy Model
------------

The energy model is based on CC2420 radio specifications:

Transmission Energy
~~~~~~~~~~~~~~~~~~~

Energy to transmit a packet:

.. math::

   E_{TX} = (V \times I_{TX} \times 8 \times (N + 6)) / R + E_{PLL}

Where:
* :math:`V` = Voltage (3.0V)
* :math:`I_{TX}` = TX current (depends on TX power level)
* :math:`N` = Packet payload size in bytes
* :math:`6` = PHY overhead (preamble + SFD + PHR)
* :math:`R` = Data rate (250,000 bps)
* :math:`E_{PLL}` = PLL turnaround overhead (10 µJ)

TX Power Levels
~~~~~~~~~~~~~~~

Available TX power levels (CC2420):

* -25 dBm: 8.5 mA
* -15 dBm: 9.9 mA
* -10 dBm: 11.0 mA
* -5 dBm: 14.0 mA
* 0 dBm: 17.4 mA (maximum)

Reception Energy
~~~~~~~~~~~~~~~~

Energy to receive a packet:

.. math::

   E_{RX} = (V \times I_{RX} \times 8 \times (N + 6)) / R + E_{PLL}

Where:
* :math:`I_{RX}` = RX current (18.8 mA constant)

Baseline Energy
~~~~~~~~~~~~~~~

Nodes consume baseline energy even when idle:

.. math::

   E_{baseline} = V \times I_{baseline} \times t

Where:
* :math:`V` = Voltage (3.0V)
* :math:`I_{baseline}` = Baseline current (``BASELINE_CURRENT``, default: 0.0001 A = 100 µA)
* :math:`t` = Time duration

Baseline energy is continuously consumed and tracked in ``energy_baseline_total``.

Battery Model
~~~~~~~~~~~~~

* **Battery Capacity**: ``BATTERY_CAPACITY`` (default: 2000 mAh)
* **Battery Voltage**: ``BATTERY_VOLTAGE`` (default: 3.0V)
* **Total Energy**: ``BATTERY_ENERGY_TOTAL`` (automatically calculated: voltage × capacity × 3600 = 21,600 Joules)
* **Minimum Threshold**: ``BATTERY_ENERGY_MIN`` (default: 1% of total = 216 Joules)
* **Shutdown**: Node shuts down when energy drops below threshold
* **Energy Tracking**: 
  * TX energy: ``energy_tx_total``
  * RX energy: ``energy_rx_total``
  * Baseline energy: ``energy_baseline_total``
  * Remaining energy: ``energy_remaining``
* **Energy Check**: Periodic check via ``check_energy_level()``
* **Shutdown Behavior**: Node stops all operations, changes color to gray, logs shutdown event

Network Recovery Protocol
-------------------------

Node Failure
~~~~~~~~~~~~

1. **Scheduled Failures**: Nodes can be scheduled to fail at specific times
2. **Failure Detection**: Node stops all operations and changes color
3. **Orphan Marking**: Children of failed node become orphans
4. **Event Logging**: Failure event logged with timestamp and role

Node Recovery
~~~~~~~~~~~~~

1. **Recovery Scheduling**: Failed nodes recover after a downtime period
2. **State Reset**: Node resets to UNDISCOVERED state
3. **Rejoin Process**: Node goes through normal discovery and join process
4. **Event Logging**: Recovery event logged with downtime and orphan count

Orphan Handling
~~~~~~~~~~~~~~~

1. **Orphan Detection**: Nodes detect when parent fails
   * Parent stops sending HEART_BEAT messages
   * Parent removed from neighbors_table
   * Parent_gui becomes invalid

2. **Become UNREGISTERED**: Orphaned nodes become UNREGISTERED
   * Address cleared (addr = None)
   * Cluster head address cleared (ch_addr = None)
   * Parent GUI cleared (parent_gui = None)
   * Member removed from parent's members_table

3. **Search for Parent**: Start searching for new parent
   * Sends JOIN_REQUEST to candidate parents
   * Can use adaptive TX power boost if ``ADAPTIVE_TX_POWER_FOR_ORPHANS`` is True
   * Boost amount: ``ORPHAN_TX_POWER_BOOST`` (default: 15 dBm)
   * Applied after 2 failed join attempts

4. **Cascade Effect**: Children of orphaned nodes also become orphans
   * ROUTER nodes handle orphaned children
   * Orphan events logged to ``orphan_events.csv``
   * Repairing method: ``REPAIRING_METHOD`` (default: 'FIND_ANOTHER_PARENT')

Cluster Optimization Protocol
------------------------------

The protocol includes mechanisms to optimize network topology:

Minimize Clusters Mode
~~~~~~~~~~~~~~~~~~~~~~

* **Goal**: Reduce the number of clusters in the network
* **Method**: Merge nearby clusters (TODO: implementation)
* **Trigger**: Periodic optimization by ROOT node

Minimize Energy Mode
~~~~~~~~~~~~~~~~~~~~

* **Goal**: Reduce overall energy consumption
* **Method**: Optimize TX power per cluster based on cluster size
* **Strategy** (implemented in ``optimize_clusters()``):
  - Small clusters (≤3 members): Lower TX power (``TX_POWER_DEFAULT - 10`` dBm, minimum ``TX_POWER_MIN``)
  - Medium clusters (4-10 members): Medium TX power (``TX_POWER_DEFAULT - 5`` dBm)
  - Large clusters (>10 members): Maximum TX power (``TX_POWER_DEFAULT``) for reliability
* **Trigger**: Periodic optimization by ROOT node (``CLUSTER_OPTIMIZATION_INTERVAL``)
* **Update**: All nodes in cluster update their TX power via ``update_cluster_tx_power()``

Packet Loss Model
-----------------

The simulation supports configurable packet loss:

* **Loss Rate**: Configurable from 0.0 to 1.0
* **Random Dropping**: Packets are randomly dropped based on loss rate
* **Type Tracking**: Loss statistics tracked per packet type
* **Impact Analysis**: Packet loss affects join time and network performance

Packet Tracing
--------------

For SENSOR_DATA packets:

1. **Route Trace**: Each packet maintains a list of visited nodes
2. **Path Recording**: Complete path recorded when packet reaches destination
3. **Hop Count**: Number of hops calculated from path length
4. **Delay Measurement**: End-to-end delay including TX/RX/processing time

Logging and Analysis
--------------------

The protocol provides comprehensive logging:

CSV Logs
~~~~~~~~

See :doc:`overview` for complete list of 24+ CSV files. Key files include:

* **registration_log.csv**: Node join times and delays (node_id, start_time, registered_time, join_delay)
* **packet_delays.csv**: Packet delivery delays with timing breakdown (base_delay, total_delay, tx_time, rx_time, processing_time, num_hops)
* **packet_paths.csv**: Complete packet paths for tracing (packet_id, path, hop_count, delay)
* **packet_routes.csv**: Packet routing decisions
* **role_changes.csv**: All role change events (node_id, old_role, new_role, time, reason)
* **recovery_events.csv**: Node failure and recovery events (node_id, failure_time, recovery_time, downtime, orphan_count)
* **orphan_events.csv**: Orphan node events (node_id, time, reason, parent_id)
* **network_snapshots.csv**: Network state snapshots at specific times
* **connectivity_over_time.csv**: Network connectivity statistics over time
* **node_power_levels_over_time.csv**: Power levels for all nodes over time
* **clusterhead_distances.csv**: Distances between cluster heads (exported periodically)
* **neighbor_distances.csv**: One-hop neighbor distances (exported periodically)
* **multihop_neighbor_table.csv**: Multi-hop neighbor information
* **cluster_members.csv**: Cluster membership information

Statistics
~~~~~~~~~~

* Average join time
* Average packet delay (with TX/RX/processing overhead)
* Recovery statistics (downtime, orphan counts)
* Packet loss statistics
* Energy consumption statistics

