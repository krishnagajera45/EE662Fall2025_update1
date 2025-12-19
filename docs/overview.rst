Overview
========

This document provides a high-level overview of the WSN Protocol Simulation project, its objectives, architecture, and key features.

Project Objectives
------------------

The WSN Protocol Simulation project implements a complete wireless sensor network protocol with the following objectives:

1. **Network Formation**: Enable nodes to discover neighbors and form a connected network
2. **Cluster Management**: Organize nodes into clusters with cluster heads for efficient communication
3. **Reliable Routing**: Provide mesh and tree routing mechanisms for packet delivery
4. **Energy Efficiency**: Track and optimize energy consumption based on CC2420 radio specifications
5. **Network Resilience**: Handle node failures and network recovery
6. **Performance Analysis**: Provide comprehensive logging and analysis tools

Architecture Overview
---------------------

The simulation consists of several key components:

Simulation Core
~~~~~~~~~~~~~~~

* **Simulator** (`wsnlab/source/wsnlab.py`): Base simulation engine using SimPy
* **Visualization** (`wsnlab/source/wsnlab_vis.py`): Tkinter-based visualization layer
* **Node Model** (`wsnlab/data_collection_tree.py`): SensorNode class implementing the protocol

Protocol Components
~~~~~~~~~~~~~~~~~~~

* **Neighbor Discovery**: One-hop and multi-hop neighbor discovery
* **Cluster Formation**: Dynamic cluster head election and member assignment
* **Routing**: Mesh-first routing with tree fallback
* **Energy Model**: CC2420 radio energy consumption tracking
* **Recovery Mechanisms**: Node failure detection and network recovery

Analysis Tools
~~~~~~~~~~~~~~

* **Plotting Scripts** (`generate_all_plots.py`): Comprehensive plotting for analysis
* **Batch Simulation** (`run_batch_simulations.py`): Run multiple simulations for statistics
* **CSV Logging**: Detailed event logging for post-simulation analysis

Key Features
------------

Neighbor Discovery
~~~~~~~~~~~~~~~~~~

* **One-Hop Discovery**: Nodes discover direct neighbors via HEART_BEAT messages
* **Multi-Hop Discovery**: Distance-vector style neighbor sharing for extended reach
* **Neighbor Table**: Maintains information about neighbors including distance, role, and hop count

Cluster Formation
~~~~~~~~~~~~~~~~~

* **Cluster Head Election**: Nodes can become cluster heads to form clusters
* **Configurable Cluster Size**: Maximum number of children per cluster is configurable
* **Cluster Head Transfer**: CH role can be transferred to reduce cluster overlap
* **Router Nodes**: Special nodes that bridge clusters without having their own cluster

Routing
~~~~~~~

* **Mesh Routing**: Uses neighbor tables for efficient local routing
* **Tree Routing**: Falls back to tree routing when mesh routing fails
* **Loop Prevention**: Route tracing prevents routing loops
* **Multi-Hop Support**: Routes packets across multiple hops efficiently

Energy Model
~~~~~~~~~~~~

* **CC2420 Radio**: Models energy consumption based on CC2420 specifications
* **TX Power Levels**: Configurable transmission power levels (-25 to 0 dBm)
* **Energy Tracking**: Tracks TX, RX, and baseline energy consumption
* **Node Shutdown**: Nodes shut down when energy drops below threshold

Network Recovery
~~~~~~~~~~~~~~~~

* **Node Failure**: Simulates node failures with scheduled recovery
* **Orphan Detection**: Detects and logs orphaned nodes
* **Automatic Recovery**: Nodes automatically rejoin network after recovery
* **Role Changes**: Tracks role changes during recovery

Analysis and Logging
~~~~~~~~~~~~~~~~~~~~

* **Packet Tracing**: Records complete paths for data packets
* **Delay Measurement**: Tracks end-to-end delays including TX/RX/processing time
* **Join Time Analysis**: Measures time for nodes to join the network
* **Comprehensive CSV Logs**: All events logged to CSV files for analysis

Configuration
-------------

All simulation parameters are configurable through `wsnlab/source/config.py`:

* Network topology parameters (node count, TX range, etc.)
* Protocol parameters (heartbeat interval, cluster size, etc.)
* Energy model parameters (battery capacity, TX power levels, etc.)
* Recovery parameters (failure rate, recovery time, etc.)

Output Files
------------

The simulation generates comprehensive CSV files for analysis. These files are automatically created during simulation execution and can be analyzed using the plotting scripts.

Core Logging Files
~~~~~~~~~~~~~~~~~~

* ``registration_log.csv`` - Node join times and registration delays
  * Columns: node_id, start_time, registered_time, join_delay
  * Records when each node joins the network

* ``packet_delays.csv`` - Packet delivery delays and timing
  * Columns: packet_type, source, dest, source_gui, dest_gui, created_at, delivered_at, base_delay, total_delay, tx_time, rx_time, processing_time, num_hops
  * Tracks end-to-end packet delivery with detailed timing breakdown

* ``packet_paths.csv`` - Complete packet routing paths
  * Columns: packet_id, packet_type, source_gui, dest_gui, path, hop_count, started_at, delivered_at, delay
  * Records full routing path for each packet

* ``packet_routes.csv`` - Packet routing decisions
  * Logs routing decisions made by nodes during packet forwarding

* ``role_changes.csv`` - Node role transition events
  * Columns: node_id, old_role, new_role, time, reason
  * Tracks all role changes (UNDISCOVERED → UNREGISTERED → REGISTERED → CLUSTER_HEAD, etc.)

Network State Files
~~~~~~~~~~~~~~~~~~~

* ``network_snapshots.csv`` - Network state snapshots at specific times
  * Columns: snapshot_label, time, total_nodes, registered_nodes, cluster_heads, routers, failed_nodes, orphan_nodes, total_energy
  * Captures network topology and state at regular intervals

* ``connectivity_over_time.csv`` - Network connectivity statistics over time
  * Columns: time, total_nodes, registered_nodes, connected_nodes, connectivity_percentage, packets_sent, packets_delivered, energy_depleted_nodes
  * Monitors network connectivity and packet delivery metrics

* ``topology.csv`` - Network topology information (if generated)

Recovery and Failure Files
~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``recovery_events.csv`` - Node failure and recovery events
  * Columns: node_id, failure_time, recovery_time, downtime, orphan_count_at_recovery, role_before_failure, role_after_recovery
  * Records all node failures and recoveries

* ``orphan_events.csv`` - Orphan node events
  * Columns: node_id, time, reason, parent_id
  * Logs when nodes become orphaned (lose parent connection)

* ``recovery_time.csv`` - Recovery time statistics (if generated)

Energy and Power Files
~~~~~~~~~~~~~~~~~~~~~~

* ``node_power_levels_over_time.csv`` - Power levels for all nodes over time
  * Columns: node_id, time, power
  * Continuous power tracking for energy analysis

* ``node_power_levels.csv`` - Final power levels per node (if generated)

* ``averagePower_by_time.csv`` - Average network power over time (generated by analysis)
  * Columns: time, avg_power, min_power, max_power, num_nodes
  * Aggregated power statistics

* ``NodePower_levels.csv`` - Current power levels for all nodes (generated by analysis)
  * Columns: node_id, current_power, last_update_time
  * Latest power state for each node

* ``nodePower_over_time.csv`` - Detailed power progression per node (generated by analysis)
  * Columns: node_id, time, power, power_consumed, power_percentage
  * Detailed power consumption tracking

* ``totalPower_by_time.csv`` - Total network power over time (generated by analysis)

Cluster and Neighbor Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``clusterhead_distances.csv`` - Distances between cluster heads
  * Columns: clusterhead_1, clusterhead_2, distance
  * Exported periodically (configurable via EXPORT_CH_CSV_INTERVAL)

* ``neighbor_distances.csv`` - One-hop neighbor distances
  * Columns: node_id, neighbor_id, distance
  * Exported periodically (configurable via EXPORT_NEIGHBOR_CSV_INTERVAL)

* ``multihop_neighbor_table.csv`` - Multi-hop neighbor information
  * Columns: node_id, neighbor_id, hop_dist, next_hop, distance, addr
  * Complete multi-hop neighbor table

* ``cluster_members.csv`` - Cluster membership information
  * Columns: cluster_head_id, member_id, member_addr
  * Cluster head and member relationships

Distance and Topology Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``node_distances.csv`` - Pairwise distances between all nodes
  * Columns: node_1, node_2, distance
  * All node-to-node distances

* ``node_distance_matrix.csv`` - Distance matrix for all nodes
  * Matrix format with node IDs as rows/columns

Other Files
~~~~~~~~~~~

* ``packet_log.csv`` - General packet logging (if enabled)
* ``wsn_log_<timestamp>.log`` - Text log file with detailed simulation events (if ENABLE_LOG_FILE is True)

File Generation
~~~~~~~~~~~~~~~

Most CSV files are created automatically when the simulation starts (via ``init_log_file()``). Some files are generated on-demand:

* Power analysis files (``averagePower_by_time.csv``, ``NodePower_levels.csv``, ``nodePower_over_time.csv``) are generated by calling ``generate_power_analysis_csvs()``
* Cluster and neighbor files are exported periodically based on configuration intervals
* Distance files are generated by calling respective export functions

All files can be analyzed using the plotting scripts in ``generate_all_plots.py`` to generate comprehensive reports.

