API Reference
=============

This document provides detailed API documentation for the key classes and functions in the WSN protocol simulation.

Core Classes
------------

SensorNode
~~~~~~~~~~

.. py:class:: SensorNode(wsn.Node)

   Main node class implementing the WSN protocol. Inherits from ``wsn.Node``.

   **Location**: ``wsnlab/data_collection_tree.py``

   **Key Attributes**:

   .. py:attribute:: role
      :type: Roles

      Current role of the node (UNDISCOVERED, UNREGISTERED, REGISTERED, CLUSTER_HEAD, ROUTER, or ROOT).

   .. py:attribute:: addr
      :type: Addr

      Network address assigned to the node.

   .. py:attribute:: ch_addr
      :type: Addr

      Cluster head address (if node is in a cluster).

   .. py:attribute:: neighbors_table
      :type: dict

      Dictionary mapping neighbor GUI ID to neighbor information:
      
      .. code-block:: python
      
         {
             neighbor_gui: {
                 'addr': Addr,
                 'ch_addr': Addr,
                 'role': Roles,
                 'distance': float,
                 'hop_count': int,
                 'arrival_time': float
             }
         }

   .. py:attribute:: multihop_neighbor_table
      :type: dict

      Dictionary for multi-hop neighbors:
      
      .. code-block:: python
      
         {
             neighbor_gui: {
                 'hop_dist': int,
                 'next_hop': int,
                 'distance': float,
                 'addr': Addr
             }
         }

   .. py:attribute:: members_table
      :type: list

      List of addresses of child nodes in the cluster.

   .. py:attribute:: energy_remaining
      :type: float

      Remaining battery energy in Joules.

   .. py:attribute:: tx_power_dbm
      :type: float

      Current transmission power in dBm.

   **Key Methods**:

   .. py:method:: update_neighbor(pck)
   
      Updates neighbor table from received HEART_BEAT message.
      
      :param pck: Heartbeat packet dictionary
      :type pck: dict

   .. py:method:: route_and_forward_package(pck)
   
      Routes and forwards a packet using mesh-first, tree-fallback strategy.
      
      :param pck: Packet dictionary with 'dest' key
      :type pck: dict
      
      Routing steps:
      1. Check multihop_neighbor_table for multi-hop route
      2. Check neighbors_table for direct neighbor
      3. Check members_table for cluster member
      4. Check same cluster routing
      5. Check child_networks_table
      6. Route to parent as fallback

   .. py:method:: send(pck)
   
      Sends a packet with energy deduction and packet loss simulation.
      
      :param pck: Packet dictionary
      :type pck: dict
      
      Deducts TX energy and handles packet loss based on ``PACKET_LOSS_RATE``.

   .. py:method:: on_receive(pck)
   
      Processes incoming packets based on node role and packet type.
      
      :param pck: Received packet dictionary
      :type pck: dict

   .. py:method:: check_energy_level()
   
      Checks if node energy is below minimum threshold and shuts down if needed.

   .. py:method:: shutdown_node(reason="Low energy")
   
      Shuts down node when energy drops below threshold.
      
      :param reason: Reason for shutdown
      :type reason: str

Energy Functions
----------------

.. py:function:: calculate_tx_energy(packet_size_bytes, tx_power_dbm=0, include_pll_overhead=True)

   Calculates transmission energy for a packet based on CC2420 specifications.
   
   :param packet_size_bytes: Packet payload size in bytes (PSDU)
   :type packet_size_bytes: int
   :param tx_power_dbm: TX power in dBm (-25 to 0)
   :type tx_power_dbm: float
   :param include_pll_overhead: Include PLL turnaround overhead
   :type include_pll_overhead: bool
   :returns: Energy in Joules
   :rtype: float
   
   Formula:
   
   .. math::
      
      E_{TX} = (V \times I_{TX} \times 8 \times (N + 6)) / R + E_{PLL}
   
   Where:
   * V = 3.0V
   * I_TX = Current for given TX power
   * N = packet_size_bytes
   * 6 = PHY overhead
   * R = 250,000 bps
   * E_PLL = 10 µJ

.. py:function:: calculate_rx_energy(packet_size_bytes, include_pll_overhead=True)

   Calculates reception energy for a packet.
   
   :param packet_size_bytes: Packet payload size in bytes
   :type packet_size_bytes: int
   :param include_pll_overhead: Include PLL turnaround overhead
   :type include_pll_overhead: bool
   :returns: Energy in Joules
   :rtype: float

.. py:function:: calculate_transmission_time(packet_size_bytes)

   Calculates transmission time for a packet.
   
   :param packet_size_bytes: Packet payload size in bytes
   :type packet_size_bytes: int
   :returns: Transmission time in seconds
   :rtype: float

.. py:function:: calculate_reception_time(packet_size_bytes)

   Calculates reception time for a packet.
   
   :param packet_size_bytes: Packet payload size in bytes
   :type packet_size_bytes: int
   :returns: Reception time in seconds
   :rtype: float

.. py:function:: estimate_packet_size(packet)

   Estimates packet size based on packet type.
   
   :param packet: Packet dictionary
   :type packet: dict
   :returns: Estimated packet size in bytes
   :rtype: int
   
   Packet size estimates:
   * HEART_BEAT: ~30 bytes
   * JOIN_REQUEST: ~20 bytes
   * JOIN_REPLY: ~25 bytes
   * SENSOR_DATA: ~60 bytes
   * NEIGHBOR_SHARE: Variable (20 + 10 × neighbors)

Logging Functions
-----------------

.. py:function:: log_packet_delivery(pck, receiver_node)

   Records end-to-end delay when packet reaches destination.
   
   :param pck: Packet dictionary
   :type pck: dict
   :param receiver_node: Receiving node object
   :type receiver_node: SensorNode
   
   Logs to ``packet_delays.csv``:
   * Base delay (simulation time difference)
   * Total delay (with TX/RX/processing time)
   * Transmission time
   * Reception time
   * Processing time
   * Number of hops

.. py:function:: record_packet_path(pck, receiver_node)

   Records complete path for SENSOR_DATA packets.
   
   :param pck: Packet dictionary
   :type pck: dict
   :param receiver_node: Receiving node object
   :type receiver_node: SensorNode
   
   Logs to ``packet_paths.csv``:
   * Packet ID
   * Source and destination
   * Complete path (node IDs)
   * Hop count
   * Delay

.. py:function:: log_registration_time(node_id, wake_time, registered_time)

   Logs node join time.
   
   :param node_id: Node GUI ID
   :type node_id: int
   :param wake_time: Time when node woke up
   :type wake_time: float
   :param registered_time: Time when node registered
   :type registered_time: float

.. py:function:: log_role_change(node_id, old_role, new_role, time, reason="")

   Logs role change events.
   
   :param node_id: Node GUI ID
   :type node_id: int
   :param old_role: Previous role
   :type old_role: Roles
   :param new_role: New role
   :type new_role: Roles
   :param time: Simulation time of change
   :type time: float
   :param reason: Reason for role change
   :type reason: str

.. py:function:: log_recovery_event(node_id, failure_time, recovery_time, orphan_count, role_before, role_after)

   Logs node recovery events.
   
   :param node_id: Node GUI ID
   :type node_id: int
   :param failure_time: Time when node failed
   :type failure_time: float
   :param recovery_time: Time when node recovered
   :type recovery_time: float
   :param orphan_count: Number of orphaned nodes at recovery
   :type orphan_count: int
   :param role_before: Role before failure
   :type role_before: Roles
   :param role_after: Role after recovery
   :type role_after: Roles

Cluster Management Functions
----------------------------

.. py:function:: get_cluster_tx_power(cluster_id)

   Gets TX power for a cluster.
   
   :param cluster_id: Cluster ID (net_addr)
   :type cluster_id: int
   :returns: TX power in dBm
   :rtype: float

.. py:function:: set_cluster_tx_power(cluster_id, tx_power_dbm)

   Sets TX power for a cluster.
   
   :param cluster_id: Cluster ID (net_addr)
   :type cluster_id: int
   :param tx_power_dbm: TX power in dBm
   :type tx_power_dbm: float
   
   Power is clamped to valid range (TX_POWER_MIN to TX_POWER_MAX).

.. py:function:: optimize_clusters()

   Runs cluster optimization protocol.
   
   Optimization modes:
   * 'CLUSTERS': Minimize number of clusters (TODO)
   * 'ENERGY': Optimize TX power per cluster to minimize energy

Base Classes
------------

Node (wsnlab.py)
~~~~~~~~~~~~~~~~

.. py:class:: Node(sim, id, pos)

   Base node class from wsnlab library.
   
   **Location**: ``wsnlab/source/wsnlab.py``
   
   **Key Methods**:
   
   .. py:method:: send(pck)
   
      Base send method that broadcasts to neighbors within TX range.
   
   .. py:method:: can_receive(pck)
   
      Checks if packet is intended for this node.
   
   .. py:method:: set_timer(name, time, *args, **kwargs)
   
      Sets a timer that will fire after specified time.
   
   .. py:method:: delayed_exec(delay, func, *args, **kwargs)
   
      Executes a function after a delay.

Simulator (wsnlab.py)
~~~~~~~~~~~~~~~~~~~~~

.. py:class:: Simulator(duration, timescale=1, seed=0)

   Base simulator class using SimPy.
   
   **Location**: ``wsnlab/source/wsnlab.py``
   
   **Key Methods**:
   
   .. py:method:: add_node(node_class, pos)
   
      Adds a node to the simulation.
   
   .. py:method:: run()
   
      Runs the simulation until duration.

Addr Class
----------

.. py:class:: Addr(net_addr, node_addr)

   Network address class with two components.
   
   **Location**: ``wsnlab/source/wsnlab.py``
   
   **Attributes**:
   
   .. py:attribute:: net_addr
      :type: int
      
      Network address (cluster ID).
   
   .. py:attribute:: node_addr
      :type: int
      
      Node address within cluster.
   
   **Methods**:
   
   .. py:method:: is_equal(other)
   
      Compares two addresses for equality.
      
      :param other: Another Addr object
      :type other: Addr
      :returns: True if addresses are equal
      :rtype: bool

Roles Enumeration
-----------------

.. py:data:: Roles

   Enumeration of node roles.
   
   Values:
   * ``UNDISCOVERED``: Node hasn't discovered network
   * ``UNREGISTERED``: Node discovered network but not joined
   * ``REGISTERED``: Node joined a cluster
   * ``CLUSTER_HEAD``: Node is a cluster head
   * ``ROUTER``: Node bridges clusters
   * ``ROOT``: Root node of the network

Plotting Functions
------------------

All plotting functions are in ``generate_all_plots.py``. There are 34 plotting functions organized into categories:

Paper Figures (Fig. 2-11)
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:function:: plot_fig2_avg_join_time_vs_network_size()

   Fig. 2: Average join time versus network size. Generates ``fig2_avg_join_time_vs_network_size.png``.

.. py:function:: plot_fig3_nodes_killed_vs_disconnected()

   Fig. 3: Nodes killed versus number of nodes disconnected (CT vs MT). Generates ``fig3_nodes_killed_vs_disconnected.png``.

.. py:function:: plot_fig3b_nodes_killed_vs_disconnected_bar()

   Fig. 3 (alt): Bar chart version of nodes killed vs disconnected. Generates ``fig3b_nodes_killed_vs_disconnected_bar.png``.

.. py:function:: plot_fig4_network_lifetime_vs_initial_energy()

   Fig. 4: Network lifetime vs initial energy for different traffic loads. Generates ``fig4_network_lifetime_vs_initial_energy.png``.

.. py:function:: plot_fig5_packets_sent_vs_delivered()

   Fig. 5: Packets sent vs packets delivered for different packet loss rates. Generates ``fig5_packets_sent_vs_delivered.png``.

.. py:function:: plot_fig6_ct_mesh_vs_ct_only()

   Fig. 6: CT+Mesh vs CT Only comparison. Generates ``fig6_ct_mesh_vs_ct_only.png``.

.. py:function:: plot_fig6_network_lifetime()

   Fig. 6 (alt): Network lifetime as a function of initial energy budget. Generates ``fig6_network_lifetime.png``.

.. py:function:: plot_fig7_energy_impact_on_lifetime_metrics()

   Fig. 7: Impact of initial energy on lifetime metrics (bar chart). Generates ``fig7_energy_impact_on_lifetime_metrics.png``.

.. py:function:: plot_fig7_avg_energy_ct_comparison()

   Fig. 7 (alt): Average Remaining Energy Over Time - CT+Mesh vs CT-only. Generates ``fig7_avg_energy_ct_comparison.png``.

.. py:function:: plot_fig8_pdr_over_time()

   Fig. 8: Packet delivery ratio (PDR) over time with multiple scenarios. Generates ``fig8_pdr_over_time.png``.

.. py:function:: plot_fig8_network_lifetime_vs_initial_energy()

   Fig. 8 (alt): Network Lifetime vs Initial Energy. Generates ``fig8_network_lifetime_vs_initial_energy.png``.

.. py:function:: plot_fig9_avg_remaining_energy_over_time()

   Fig. 9: Average remaining energy over time for different traffic loads. Generates ``fig9_avg_remaining_energy_over_time.png``.

.. py:function:: plot_fig10_fraction_connected_nodes_over_time()

   Fig. 10: Fraction of connected nodes over time for different traffic loads. Generates ``fig10_fraction_connected_nodes_over_time.png``.

.. py:function:: plot_fig11_cdf_node_lifetimes()

   Fig. 11: CDF of node lifetimes for cluster heads vs leaf nodes. Generates ``fig11_cdf_node_lifetimes.png``.

General Analysis Plots
~~~~~~~~~~~~~~~~~~~~~~

.. py:function:: plot_join_time_analysis()

   Generates join time analysis plots (histogram, CDF, box plot). Generates ``join_time_analysis.png``.

.. py:function:: plot_cluster_analysis()

   Generates cluster formation analysis plots. Generates ``cluster_analysis.png``.

.. py:function:: plot_tx_power_analysis()

   Generates TX power vs energy consumption plots. Generates ``tx_power_analysis.png``.

.. py:function:: plot_network_lifetime()

   Generates network lifetime vs packet size plots. Generates ``network_lifetime.png``.

.. py:function:: plot_packet_tracing()

   Generates packet path visualization plots. Generates ``packet_tracing.png``.

.. py:function:: plot_protocol_metrics()

   Generates comprehensive protocol performance metrics. Generates ``protocol_metrics.png``.

.. py:function:: plot_config_parameters()

   Generates configuration parameters analysis plots. Generates ``config_parameters.png``.

.. py:function:: plot_batch_simulation_averages()

   Generates average statistics from batch simulations. Generates ``batch_simulation_averages.png``.

.. py:function:: plot_packet_loss_vs_join_time()

   Generates packet loss impact on join time plots. Generates ``packet_loss_vs_join_time.png``.

.. py:function:: plot_config_parameters_over_time()

   Generates network behavior over time plots. Generates ``config_parameters_over_time.png``.

.. py:function:: plot_max_nodes_vs_clusters()

   Generates cluster size vs cluster count plots. Generates ``max_nodes_vs_clusters.png``.

.. py:function:: plot_tx_power_vs_network_lifetime()

   Generates TX power impact on network lifetime plots. Generates ``tx_power_vs_network_lifetime.png``.

.. py:function:: plot_packet_size_vs_network_lifetime()

   Generates packet size impact on network lifetime plots. Generates ``packet_size_vs_network_lifetime.png``.

CT vs MT Comparison Plots
~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:function:: plot_network_discovery_rate()

   Network Discovery/Registration Rate (CT vs MT). Generates ``network_discovery_rate.png``.

.. py:function:: plot_packet_delivery_with_loss()

   Packet Delivery Performance with Packet Loss (CT vs MT). Generates ``packet_delivery_with_loss.png``.

.. py:function:: plot_registration_time_vs_packet_loss()

   Node Registration Time vs Packet Loss (CT vs MT). Generates ``registration_time_vs_packet_loss.png``.

.. py:function:: plot_packet_delivery_time_vs_nodes()

   Average Time to Deliver a Packet vs Number of Nodes (CT vs MT). Generates ``packet_delivery_time_vs_nodes.png``.

.. py:function:: plot_energy_vs_nodes()

   Average Energy Consumption vs Number of Nodes (CT vs MT). Generates ``energy_vs_nodes.png``.

.. py:function:: plot_total_energy_vs_time()

   Total System Energy vs Time (CT vs MT). Generates ``total_energy_vs_time.png``.

Recovery Analysis Plots
~~~~~~~~~~~~~~~~~~~~~~~

.. py:function:: plot_nodes_discovered_vs_killed()

   Number of Nodes Discovered vs Number of Nodes Killed (Recovery Analysis). Generates ``nodes_discovered_vs_killed.png``.

Data Loading Functions
----------------------

.. py:function:: load_join_times(csv_file="registration_log.csv")

   Loads join times from registration log.
   
   :param csv_file: Path to registration log CSV
   :type csv_file: str
   :returns: Tuple of (join_times list, node_ids list)
   :rtype: tuple

.. py:function:: load_packet_paths(csv_file="packet_paths.csv", max_packets=100)

   Loads packet paths from CSV.
   
   :param csv_file: Path to packet paths CSV
   :type csv_file: str
   :param max_packets: Maximum number of packets to load
   :type max_packets: int
   :returns: List of path dictionaries
   :rtype: list

.. py:function:: load_all_metrics()

   Loads all available metrics from CSV files.
   
   :returns: Dictionary with metrics
   :rtype: dict
   
   Returns dictionary with keys:
   * 'join_times': List of join times
   * 'packet_delays': List of packet delays
   * 'base_delays': List of base delays
   * 'total_delays': List of total delays
   * 'role_changes': List of role change events
   * 'recoveries': List of recovery events
   * 'orphans': List of orphan events
   * 'cluster_heads': List of cluster head IDs

Utility Functions
-----------------

.. py:function:: init_log_file()

   Initialize log files and CSV headers for simulation.
   
   Creates timestamped log file and initializes CSV files with headers:
   * packet_delays.csv
   * registration_log.csv
   * packet_paths.csv
   * recovery_events.csv
   * orphan_events.csv
   * role_changes.csv
   * network_snapshots.csv
   * connectivity_over_time.csv
   
   :returns: Log file name if created, None otherwise
   :rtype: str or None

.. py:function:: write_log(node_ref, message, sim_time=None)

   Write log message to file with node ID and timestamp.
   
   :param node_ref: Node object or node ID
   :type node_ref: SensorNode or int
   :param message: Log message
   :type message: str
   :param sim_time: Simulation time (optional)
   :type sim_time: float or None

.. py:function:: log_to_console_and_file(message)

   Write message to both console and log file.
   
   :param message: Message to log
   :type message: str

.. py:function:: take_network_snapshot(snapshot_label="", sim_time=None)

   Capture network state snapshot as CSV and PNG.
   
   :param snapshot_label: Label for the snapshot
   :type snapshot_label: str
   :param sim_time: Simulation time (optional, uses current time if None)
   :type sim_time: float or None
   
   Creates snapshot with:
   * Network topology (CSV)
   * Visualization (PNG)
   * Node states, roles, positions, energy levels

.. py:function:: check_and_log_connectivity(sim_time=None)

   Check network connectivity and log statistics.
   
   :param sim_time: Simulation time (optional)
   :type sim_time: float or None
   :returns: True if connectivity threshold met, False otherwise
   :rtype: bool
   
   Logs to connectivity_over_time.csv with:
   * Total nodes
   * Registered nodes
   * Connected nodes
   * Connectivity percentage
   * Packet statistics
   * Energy depleted nodes

CSV Export Functions
--------------------

.. py:function:: write_cluster_members_csv(path="cluster_members.csv")

   Write cluster membership information to CSV.
   
   :param path: Output CSV file path
   :type path: str
   
   Exports cluster head and member relationships.

.. py:function:: write_multihop_neighbor_table_csv(path="multihop_neighbor_table.csv")

   Write multi-hop neighbor table to CSV file.
   
   :param path: Output CSV file path
   :type path: str
   
   Exports multi-hop neighbor information including hop distances.

.. py:function:: generate_power_analysis_csvs()

   Generate power analysis CSV files from simulation data.
   
   Reads from ``node_power_levels_over_time.csv`` and creates:
   * ``averagePower_by_time.csv`` - Average power over time with min/max/num_nodes
   * ``NodePower_levels.csv`` - Current power levels per node with last update time
   * ``nodePower_over_time.csv`` - Detailed power progression with consumption and percentage
   
   All files are written to the current directory.

Network Creation
----------------

.. py:function:: create_network(node_class, number_of_nodes=100)

   Create network of sensor nodes at random positions.
   
   :param node_class: Node class to instantiate
   :type node_class: class
   :param number_of_nodes: Number of nodes to create
   :type number_of_nodes: int
   
   Places nodes in a grid pattern with random offsets.
   Sets arrival times and initializes node properties.

