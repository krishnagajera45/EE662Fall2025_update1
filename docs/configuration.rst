Configuration Guide
===================

This document describes all configuration parameters available in the WSN protocol simulation and how to customize them.

Configuration File
------------------

All configuration parameters are defined in ``wsnlab/source/config.py``. This file uses Python syntax and can be edited with any text editor. Parameters are organized into sections with clear comments.

Network Addressing
------------------

.. code-block:: python

   BROADCAST_NET_ADDR = 255  # Network address for broadcast messages
   BROADCAST_NODE_ADDR = 255  # Node address for broadcast messages
   TOTAL_BITS = 16  # Total bits available for network addressing

**BROADCAST_NET_ADDR**: Network address used for broadcast messages (255).

**BROADCAST_NODE_ADDR**: Node address used for broadcast messages (255).

**TOTAL_BITS**: Total bits available for network addressing (16 bits default). Used to calculate cluster and node address space.

Network Properties
------------------

Node Configuration
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   NODE_TX_RANGE = 141  # Transmission range in meters
   NODE_ARRIVAL_MAX = 50  # Maximum wake-up time in seconds

**NODE_TX_RANGE**: Transmission range of nodes in meters. Increase for better connectivity, decrease for more realistic scenarios. Current value: 141 meters.

**NODE_ARRIVAL_MAX**: Maximum time (in simulation seconds) for nodes to wake up. Lower values result in faster network formation. Current value: 50 seconds.

Simulation Configuration
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   SIM_NODE_COUNT = 100  # Number of nodes in simulation
   SIM_NODE_PLACING_CELL_SIZE = 93  # Grid cell size for node placement (meters)
   SIM_DURATION = 5000  # Simulation duration in seconds
   SIM_TIME_SCALE = 0.00001  # Real time per simulation second
   SIM_TERRAIN_SIZE = (1200, 1200)  # Terrain size in meters
   SIM_VISUALIZATION = True  # Enable/disable visualization
   SCALE = 0.8  # Scale factor for visualization and node spacing
   SIM_SEED = 50  # Random seed for reproducibility
   SIM_TITLE = 'Data Collection Tree'  # Title displayed in visualization window
   SIM_BACKGROUND_COLOR = 'white'  # Background color for visualization window

**SIM_NODE_COUNT**: Total number of nodes in the simulation. Current value: 100.

**SIM_NODE_PLACING_CELL_SIZE**: Grid cell size for node placement in meters. Controls spacing between nodes. Current value: 93 meters. Note: Maintain ratio with NODE_TX_RANGE (approximately 1.52:1) for full connectivity.

**SIM_DURATION**: How long the simulation runs (in simulation seconds). Current value: 5000 seconds.

**SIM_TIME_SCALE**: Real-time duration of 1 simulation second. Lower values make simulation run faster. Current value: 0.00001.

**SIM_TERRAIN_SIZE**: Size of the simulation terrain in meters (width, height). Current value: (1200, 1200).

**SIM_VISUALIZATION**: Set to ``False`` to disable visualization (faster execution).

**SCALE**: Scale factor applied to visualization and node spacing. Current value: 0.8.

**SIM_SEED**: Random seed for reproducible simulations. Change for different network topologies. Current value: 50.

**SIM_TITLE**: Title displayed in visualization window. Default: 'Data Collection Tree'.

**SIM_BACKGROUND_COLOR**: Background color for visualization window. Default: 'white'.

Cluster Formation
-----------------

Cluster Size Control
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   MAX_CHILD_NODES_ALLOWED_PER_CLUSTER = 20  # Maximum children per cluster
   TOTAL_BITS = 16  # Total address bits
   bits_child = math.ceil(math.log2(MAX_CHILD_NODES_ALLOWED_PER_CLUSTER))
   bits_cluster = TOTAL_BITS - bits_child
   NUM_OF_CLUSTERS = (1 << bits_cluster) - 1  # Maximum number of clusters

**MAX_CHILD_NODES_ALLOWED_PER_CLUSTER**: Maximum number of child nodes allowed in each cluster. This directly controls cluster size and network topology.

* Lower values → More clusters, smaller clusters
* Higher values → Fewer clusters, larger clusters

**TOTAL_BITS**: Total number of bits for network addressing (16 bits default).

**NUM_OF_CLUSTERS**: Automatically calculated maximum number of clusters based on address space.

**NUM_OF_CHILDREN**: Legacy alias for MAX_CHILD_NODES_ALLOWED_PER_CLUSTER (backward compatibility).

Cluster Head Transfer
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   ENABLE_CH_TRANSFER = True  # Enable CH role transfer
   MIN_MEMBERS_FOR_TRANSFER = 1  # Minimum members before transfer

**ENABLE_CH_TRANSFER**: Enable cluster head role transfer to reduce cluster overlap.

**MIN_MEMBERS_FOR_TRANSFER**: Minimum number of members required before CH can transfer role.

Proactive CH Creation
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   ENABLE_PROACTIVE_CH_CREATION = True  # Allow proactive CH creation
   PROACTIVE_CH_TIMER = 20  # Seconds before REGISTERED node becomes CH
   UNREGISTERED_CH_TRIGGER_THRESHOLD = 1  # Failed attempts before triggering CH creation
   ADAPTIVE_TX_POWER_FOR_ORPHANS = True  # Boost TX power for isolated nodes
   ORPHAN_TX_POWER_BOOST = 15  # TX power boost in dBm for orphaned nodes

**ENABLE_PROACTIVE_CH_CREATION**: Allow REGISTERED nodes to proactively become cluster heads. Current value: True.

**PROACTIVE_CH_TIMER**: Time (seconds) after registration before node can become CH if no JOIN_REQUEST received. Current value: 20 seconds.

**UNREGISTERED_CH_TRIGGER_THRESHOLD**: Number of failed join attempts before UNREGISTERED node triggers CH creation. Current value: 1 (very aggressive for connectivity).

**ADAPTIVE_TX_POWER_FOR_ORPHANS**: Automatically boost transmission power for isolated/orphaned nodes. Current value: True.

**ORPHAN_TX_POWER_BOOST**: Transmission power boost in dBm for orphaned nodes. Current value: 15 dBm.

Protocol Parameters
-------------------

Heartbeat and Discovery
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   HEARTH_BEAT_TIME_INTERVAL = 3  # Heartbeat interval in seconds
   NEIGHBOR_SHARE_INTERVAL = 30  # Neighbor sharing interval
   MAX_HOP_DISTANCE = 3  # Maximum hop distance for multi-hop discovery
   ENABLE_MULTIHOP_DISCOVERY = True  # Enable multi-hop neighbor discovery

**HEARTH_BEAT_TIME_INTERVAL**: How often nodes send HEART_BEAT messages. Lower values = faster discovery but more overhead. Current value: 3 seconds.

**NEIGHBOR_SHARE_INTERVAL**: How often nodes share their neighbor tables. Lower values = faster multi-hop discovery.

**MAX_HOP_DISTANCE**: Maximum hop distance to track in multi-hop neighbor table.

**ENABLE_MULTIHOP_DISCOVERY**: Enable/disable multi-hop neighbor discovery.

Routing Configuration
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   ENABLE_MESH_ROUTING = True  # Enable mesh routing (tries mesh first, then tree)
   ENABLE_TREE_ROUTING = True  # Enable tree routing (fallback when mesh routing fails)

**ENABLE_MESH_ROUTING**: Enable mesh routing. If True, routing tries mesh first, then falls back to tree routing. Current value: True.

**ENABLE_TREE_ROUTING**: Enable tree routing. If True, tree routing is used when mesh routing fails. Current value: True.

Network Repair
~~~~~~~~~~~~~~

.. code-block:: python

   REPAIRING_METHOD = 'FIND_ANOTHER_PARENT'  # Method for network repair

**REPAIRING_METHOD**: Method for network repair when nodes become orphaned. Options: 'FIND_ANOTHER_PARENT' or 'ALL_ORPHAN'. Current value: 'FIND_ANOTHER_PARENT'.

Data Traffic
~~~~~~~~~~~~

.. code-block:: python

   DATA_PACKET_INTERVAL = 10  # Seconds between data packet injections

**DATA_PACKET_INTERVAL**: How often each node sends a random data packet to ROOT.

Packet Loss
-----------

.. code-block:: python

   PACKET_LOSS_RATE = 0  # Packet loss rate (0.0 to 1.0)
   ENABLE_PACKET_LOSS_DEBUG = True  # Debug logging for packet loss

**PACKET_LOSS_RATE**: Fraction of packets randomly dropped (0.0 = no loss, 1.0 = all dropped).

* Use values like 0.0001 (10^-4) to 0.001 (10^-3) for realistic scenarios
* Higher values test network resilience

**ENABLE_PACKET_LOSS_DEBUG**: Enable debug logging for packet loss events.

Packet Visualization
--------------------

.. code-block:: python

   ENABLE_PACKET_VISUALIZATION = True  # Enable visualization of packet traces
   PACKET_TRACE_DURATION = 10.0  # Duration to keep packet trace lines visible (seconds)

**ENABLE_PACKET_VISUALIZATION**: Enable visualization of packet traces during simulation. Current value: True.

**PACKET_TRACE_DURATION**: Duration to keep packet trace lines visible in visualization window. Current value: 10.0 seconds.

Energy Model
------------

Energy Model Toggle
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   ENABLE_ENERGY_MODEL = True  # Enable energy consumption tracking
   ENABLE_ENERGY_DEBUG = True  # Debug logging for energy

**ENABLE_ENERGY_MODEL**: Enable/disable energy consumption tracking and node shutdown.

**ENABLE_ENERGY_DEBUG**: Enable detailed energy consumption logging.

CC2420 Radio Specifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   CC2420_DATA_RATE = 250000  # bits per second (250 kbps)
   CC2420_VOLTAGE = 3.0  # Volts
   CC2420_PHY_OVERHEAD = 6  # bytes (preamble + SFD + PHR)
   CC2420_PLL_OVERHEAD_ENERGY = 10e-6  # Joules (10 µJ)
   CC2420_RX_CURRENT = 18.8  # mA (receive current)

**CC2420_DATA_RATE**: Radio data rate in bits per second.

**CC2420_VOLTAGE**: Supply voltage in Volts.

**CC2420_PHY_OVERHEAD**: Physical layer overhead in bytes.

**CC2420_PLL_OVERHEAD_ENERGY**: PLL turnaround overhead energy in Joules.

**CC2420_RX_CURRENT**: Receive current in milliamperes.

TX Power Configuration
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   TX_POWER_LEVELS = {
       -25: 8.5,   # mA at -25 dBm
       -15: 9.9,   # mA at -15 dBm
       -10: 11.0,  # mA at -10 dBm
       -5: 14.0,   # mA at -5 dBm
       0: 17.4     # mA at 0 dBm (maximum)
   }
   
   TX_POWER_MIN = -25  # Minimum TX power in dBm
   TX_POWER_MAX = 0    # Maximum TX power in dBm
   TX_POWER_DEFAULT = 0  # Default TX power in dBm
   USE_GLOBAL_TX_POWER = False  # Use same power for all vs per-cluster

**TX_POWER_LEVELS**: Dictionary mapping TX power (dBm) to current consumption (mA).

**TX_POWER_MIN/MAX**: Valid range for TX power.

**TX_POWER_DEFAULT**: Default TX power used when not specified per-cluster.

**USE_GLOBAL_TX_POWER**: If ``True``, all nodes use same TX power. If ``False``, each cluster can have different power.

Battery Configuration
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   BATTERY_VOLTAGE = 3.0  # Volts
   BATTERY_CAPACITY = 2000  # mAh
   BATTERY_ENERGY_TOTAL = 21600  # Joules (calculated)
   BATTERY_ENERGY_MIN = 216  # Joules (1% of total)
   BASELINE_CURRENT = 0.0001  # Amperes (100 µA)

**BATTERY_VOLTAGE**: Battery voltage in Volts.

**BATTERY_CAPACITY**: Battery capacity in milliampere-hours (mAh).

**BATTERY_ENERGY_TOTAL**: Total battery energy in Joules (automatically calculated).

**BATTERY_ENERGY_MIN**: Minimum energy threshold. Nodes shut down below this.

**BASELINE_CURRENT**: Baseline current consumption when node is idle (in Amperes).

Network Recovery
----------------

Recovery Toggle
~~~~~~~~~~~~~~~

.. code-block:: python

   ENABLE_NODE_FAILURE_RECOVERY = True  # Enable node failure simulation
   ENABLE_RECOVERY_DEBUG = True  # Debug logging for recovery

**ENABLE_NODE_FAILURE_RECOVERY**: Enable/disable node failure and recovery simulation.

**ENABLE_RECOVERY_DEBUG**: Enable detailed recovery event logging.

Failure Scheduling
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   NODE_FAILURE_START_TIME = 200  # When failures start (simulation time)
   NODE_FAILURE_INTERVAL = 100  # Time between failures
   NODE_RECOVERY_TIME_MIN = 50  # Minimum recovery time
   NODE_RECOVERY_TIME_MAX = 150  # Maximum recovery time
   NUM_NODES_TO_FAIL = 2  # Number of nodes to fail

**NODE_FAILURE_START_TIME**: Simulation time when first failure occurs.

**NODE_FAILURE_INTERVAL**: Time between consecutive node failures.

**NODE_RECOVERY_TIME_MIN/MAX**: Range for recovery time (randomly selected).

**NUM_NODES_TO_FAIL**: Total number of nodes that will fail during simulation.

Visualization Highlights
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   FAILURE_HIGHLIGHT_DURATION = 10  # Duration to highlight failed nodes in red (seconds)
   ORPHAN_HIGHLIGHT_DURATION = 10  # Duration to highlight orphaned nodes in orange (seconds)

**FAILURE_HIGHLIGHT_DURATION**: Duration to highlight failed nodes in red color. Current value: 10 seconds.

**ORPHAN_HIGHLIGHT_DURATION**: Duration to highlight orphaned nodes in orange color. Current value: 10 seconds.

Network Snapshots
-----------------

The simulation can capture network state snapshots at specific times:

.. code-block:: python

   ENABLE_NETWORK_SNAPSHOTS = True  # Enable network state snapshots
   SNAPSHOT_FOLDER = "snapshots"  # Folder name for storing snapshot PNG files
   CAPTURE_SIMULATION_WINDOW = True  # Capture actual simulation window
   SNAPSHOT_BEFORE_T1 = True  # Take snapshot before T1 (baseline network state)
   SNAPSHOT_AT_T1 = True  # Take snapshot at T1 (when failures occur)
   SNAPSHOT_T1_T2_AFTER_FAILURE = True  # Take snapshot between T1-T2 (after failure)
   SNAPSHOT_T1_T2_DELAY = 5  # Delay after T1 before taking T1-T2 snapshot (seconds)
   SNAPSHOT_T2_T3_RECOVERY = True  # Take snapshot during T2-T3 (recovery in progress)
   SNAPSHOT_AT_T3_AFTER_RECOVERY = True  # Take snapshot at T3 (after recovery completes)
   SNAPSHOT_AFTER_T3_INTERVAL = 50  # Time interval for snapshots after T3 (seconds)
   SNAPSHOT_AFTER_T3_COUNT = 3  # Number of snapshots to take after T3
   SNAPSHOT_FINAL_STATE = True  # Take final snapshot at simulation end

**ENABLE_NETWORK_SNAPSHOTS**: Enable network state snapshots (CSV and PNG files). Current value: True.

**SNAPSHOT_FOLDER**: Folder name for storing snapshot PNG files. Default: "snapshots".

**CAPTURE_SIMULATION_WINDOW**: Capture actual simulation window (requires PIL/Pillow). Current value: True.

**SNAPSHOT_BEFORE_T1**: Take snapshot before T1 (baseline network state). Current value: True.

**SNAPSHOT_AT_T1**: Take snapshot at T1 (when failures occur). Current value: True.

**SNAPSHOT_T1_T2_AFTER_FAILURE**: Take snapshot between T1-T2 (after failure, shows orphans). Current value: True.

**SNAPSHOT_T1_T2_DELAY**: Delay after T1 before taking T1-T2 snapshot. Current value: 5 seconds.

**SNAPSHOT_T2_T3_RECOVERY**: Take snapshot during T2-T3 (recovery in progress). Current value: True.

**SNAPSHOT_AT_T3_AFTER_RECOVERY**: Take snapshot at T3 (after recovery completes). Current value: True.

**SNAPSHOT_AFTER_T3_INTERVAL**: Time interval for snapshots after T3. Current value: 50 seconds.

**SNAPSHOT_AFTER_T3_COUNT**: Number of snapshots to take after T3. Current value: 3.

**SNAPSHOT_FINAL_STATE**: Take final snapshot at simulation end. Current value: True.

Cluster Optimization
--------------------

.. code-block:: python

   ENABLE_CLUSTER_OPTIMIZATION = True  # Enable optimization protocol
   CLUSTER_OPTIMIZATION_MODE = 'ENERGY'  # 'CLUSTERS' or 'ENERGY'
   CLUSTER_OPTIMIZATION_INTERVAL = 100  # Optimization interval

**ENABLE_CLUSTER_OPTIMIZATION**: Enable cluster optimization protocol.

**CLUSTER_OPTIMIZATION_MODE**: 
* ``'CLUSTERS'``: Minimize number of clusters (TODO: implementation)
* ``'ENERGY'``: Minimize energy consumption via TX power optimization

**CLUSTER_OPTIMIZATION_INTERVAL**: How often optimization runs (simulation seconds).

Debugging and Logging
---------------------

Debug Flags
~~~~~~~~~~~

.. code-block:: python

   ENABLE_LOG_FILE = True  # Write log file
   ENABLE_ROUTING_DEBUG = True  # Routing debug messages
   ENABLE_CLUSTER_DEBUG = True  # Cluster debug messages
   ENABLE_NEIGHBOR_DEBUG = True  # Neighbor discovery debug

**ENABLE_LOG_FILE**: Enable/disable timestamped log file creation.

**ENABLE_ROUTING_DEBUG**: Enable detailed routing decision logging.

**ENABLE_CLUSTER_DEBUG**: Enable cluster formation and management logging.

**ENABLE_NEIGHBOR_DEBUG**: Enable neighbor discovery logging.

CSV Export Intervals
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   EXPORT_CH_CSV_INTERVAL = 10  # Cluster head CSV export interval
   EXPORT_NEIGHBOR_CSV_INTERVAL = 10  # Neighbor CSV export interval

**EXPORT_CH_CSV_INTERVAL**: How often to export cluster head distances CSV.

**EXPORT_NEIGHBOR_CSV_INTERVAL**: How often to export neighbor distances CSV.

Configuration Examples
----------------------

Small Network (20 nodes)
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   SIM_NODE_COUNT = 20
   MAX_CHILD_NODES_ALLOWED_PER_CLUSTER = 5
   SIM_DURATION = 2000

Large Network (200 nodes)
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   SIM_NODE_COUNT = 200
   MAX_CHILD_NODES_ALLOWED_PER_CLUSTER = 30
   SIM_DURATION = 10000

Energy-Critical Scenario
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   ENABLE_ENERGY_MODEL = True
   TX_POWER_DEFAULT = -15  # Lower power for energy savings
   BASELINE_CURRENT = 0.00005  # Lower baseline current
   DATA_PACKET_INTERVAL = 30  # Less frequent data packets

High Reliability Scenario
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   TX_POWER_DEFAULT = 0  # Maximum power
   PACKET_LOSS_RATE = 0  # No packet loss
   HEARTH_BEAT_TIME_INTERVAL = 3  # More frequent heartbeats (or lower for even faster)

Testing Recovery
~~~~~~~~~~~~~~~~

.. code-block:: python

   ENABLE_NODE_FAILURE_RECOVERY = True
   NUM_NODES_TO_FAIL = 5
   NODE_FAILURE_START_TIME = 100
   NODE_RECOVERY_TIME_MIN = 30
   NODE_RECOVERY_TIME_MAX = 60

Testing Packet Loss
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   PACKET_LOSS_RATE = 0.001  # 0.1% packet loss
   ENABLE_PACKET_LOSS_DEBUG = True

Best Practices
--------------

1. **Start with defaults**: Use default values first, then adjust based on results
2. **Change one parameter at a time**: Makes it easier to understand effects
3. **Use SIM_SEED**: Set a fixed seed for reproducible results during testing
4. **Disable visualization**: Set ``SIM_VISUALIZATION = False`` for faster batch runs
5. **Adjust cluster size**: Balance between cluster count and cluster size based on network size
6. **Monitor energy**: Enable energy debug to understand consumption patterns
7. **Test recovery**: Enable recovery to test network resilience

