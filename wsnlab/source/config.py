import math

# ============================================================================
# NETWORK ADDRESSING
# ============================================================================
BROADCAST_NET_ADDR = 255  # Network address for broadcast messages
BROADCAST_NODE_ADDR = 255  # Node address for broadcast messages
TOTAL_BITS = 16  # Total bits available for network addressing

# ============================================================================
# NODE PROPERTIES
# ============================================================================
NODE_TX_RANGE = 141  # Transmission range of nodes in meters
NODE_ARRIVAL_MAX = 50  # Maximum time delay before node wakes up (seconds)

# ============================================================================
# CLUSTER FORMATION
# ============================================================================
MAX_CHILD_NODES_ALLOWED_PER_CLUSTER = 20  # Maximum number of child nodes per cluster head
bits_child = math.ceil(math.log2(MAX_CHILD_NODES_ALLOWED_PER_CLUSTER))  # Bits needed for child node addressing
bits_cluster = TOTAL_BITS - bits_child  # Bits available for cluster network addressing
NUM_OF_CLUSTERS = (1 << bits_cluster) - 1  # Maximum number of clusters that can be created
NUM_OF_CHILDREN = MAX_CHILD_NODES_ALLOWED_PER_CLUSTER  # Legacy alias for backward compatibility

# ============================================================================
# SIMULATION SETTINGS
# ============================================================================
SIM_NODE_COUNT = 100  # Total number of nodes in the simulation
SIM_NODE_PLACING_CELL_SIZE = 93  # Grid cell size for node placement (meters)
SIM_DURATION = 5000  # Total simulation duration (seconds)
SIM_TIME_SCALE = 0.00001  # Real-time scaling factor (seconds per simulation second)
SIM_TERRAIN_SIZE = (1200, 1200)  # Size of simulation terrain (width, height in meters)
SIM_TITLE = 'Data Collection Tree'  # Title displayed in visualization window
SIM_VISUALIZATION = True  # Enable/disable visualization window
SCALE = 0.8  # Scale factor applied to visualization and node spacing
SIM_SEED = 50  # Random seed for reproducible simulation results
SIM_BACKGROUND_COLOR = 'white'  # Background color for visualization window

# ============================================================================
# APPLICATION PROTOCOL
# ============================================================================
HEARTH_BEAT_TIME_INTERVAL = 3  # Time interval between heartbeat messages (seconds)
REPAIRING_METHOD = 'FIND_ANOTHER_PARENT'  # Method for network repair: 'FIND_ANOTHER_PARENT' or 'ALL_ORPHAN'
EXPORT_CH_CSV_INTERVAL = 10  # Interval for exporting cluster head data to CSV (simulation time)
EXPORT_NEIGHBOR_CSV_INTERVAL = 10  # Interval for exporting neighbor data to CSV (simulation time)

# ============================================================================
# NEIGHBOR DISCOVERY
# ============================================================================
ENABLE_MULTIHOP_DISCOVERY = True  # Enable multi-hop neighbor discovery mechanism
MAX_HOP_DISTANCE = 3  # Maximum hop distance for neighbor discovery
NEIGHBOR_SHARE_INTERVAL = 30  # Time interval for sharing neighbor information (simulation time)
ENABLE_NEIGHBOR_DEBUG = True  # Enable debug logging for neighbor discovery

# ============================================================================
# ROUTING & DEBUG
# ============================================================================
ENABLE_LOG_FILE = True  # Enable writing simulation events to log file
ENABLE_ROUTING_DEBUG = True  # Enable debug logging for mesh/tree routing
ENABLE_CLUSTER_DEBUG = True  # Enable debug logging for cluster and member tables
ENABLE_MESH_ROUTING = True  # Enable mesh routing (tries mesh first, then tree)
ENABLE_TREE_ROUTING = True  # Enable tree routing (fallback when mesh routing fails)
ENABLE_PACKET_VISUALIZATION = True  # Enable visualization of packet traces during simulation
PACKET_TRACE_DURATION = 10.0  # Duration to keep packet trace lines visible (seconds)

# ============================================================================
# DATA TRAFFIC
# ============================================================================
DATA_PACKET_INTERVAL = 10  # Time interval between data packet transmissions per node (seconds)

# ============================================================================
# CHANNEL MODEL
# ============================================================================
PACKET_LOSS_RATE = 0  # Packet loss rate (0.0 to 1.0, where 1.0 = 100% loss)
ENABLE_PACKET_LOSS_DEBUG = True  # Enable debug logging for packet loss events

# ============================================================================
# NETWORK RECOVERY
# ============================================================================
ENABLE_NODE_FAILURE_RECOVERY = True  # Enable random node failures for testing recovery algorithms
NODE_FAILURE_START_TIME = 200  # Simulation time when node failures begin (T1)
NODE_FAILURE_INTERVAL = 100  # Time interval between consecutive node failures (seconds)
NODE_RECOVERY_TIME_MIN = 50  # Minimum time before failed node recovers (T2-T3 period)
NODE_RECOVERY_TIME_MAX = 150  # Maximum time before failed node recovers (T3)
NUM_NODES_TO_FAIL = 2  # Number of random nodes to fail during simulation
ENABLE_RECOVERY_DEBUG = True  # Enable debug logging for network recovery events

# ============================================================================
# VISUALIZATION HIGHLIGHTS
# ============================================================================
FAILURE_HIGHLIGHT_DURATION = 10  # Duration to highlight failed nodes in red (seconds)
ORPHAN_HIGHLIGHT_DURATION = 10  # Duration to highlight orphaned nodes in orange (seconds)

# ============================================================================
# NETWORK SNAPSHOTS
# ============================================================================
ENABLE_NETWORK_SNAPSHOTS = True  # Enable network state snapshots (CSV and PNG files)
SNAPSHOT_FOLDER = "snapshots"  # Folder name for storing snapshot PNG files
CAPTURE_SIMULATION_WINDOW = True  # Capture actual simulation window (requires PIL/Pillow)
SNAPSHOT_BEFORE_T1 = True  # Take snapshot before T1 (baseline network state)
SNAPSHOT_AT_T1 = True  # Take snapshot at T1 (when failures occur)
SNAPSHOT_T1_T2_AFTER_FAILURE = True  # Take snapshot between T1-T2 (after failure, shows orphans)
SNAPSHOT_T1_T2_DELAY = 5  # Delay after T1 before taking T1-T2 snapshot (seconds)
SNAPSHOT_T2_T3_RECOVERY = True  # Take snapshot during T2-T3 (recovery in progress)
SNAPSHOT_AT_T3_AFTER_RECOVERY = True  # Take snapshot at T3 (after recovery completes)
SNAPSHOT_AFTER_T3_INTERVAL = 50  # Time interval for snapshots after T3 (seconds)
SNAPSHOT_AFTER_T3_COUNT = 3  # Number of snapshots to take after T3
SNAPSHOT_FINAL_STATE = True  # Take final snapshot at simulation end

# ============================================================================
# CLUSTER HEAD TRANSFER
# ============================================================================
ENABLE_CH_TRANSFER = True  # Enable cluster head role transfer to reduce cluster overlap
MIN_MEMBERS_FOR_TRANSFER = 1  # Minimum number of members required before CH can transfer role

# ============================================================================
# CLUSTER HEAD CREATION
# ============================================================================
ENABLE_PROACTIVE_CH_CREATION = True  # Allow registered nodes to proactively become cluster heads
PROACTIVE_CH_TIMER = 20  # Time after registration before node can become CH (seconds)
UNREGISTERED_CH_TRIGGER_THRESHOLD = 1  # Failed join attempts before unregistered node creates CH
ADAPTIVE_TX_POWER_FOR_ORPHANS = True  # Automatically boost transmission power for isolated nodes
ORPHAN_TX_POWER_BOOST = 15  # Transmission power boost for orphaned nodes (dBm)

# ============================================================================
# ENERGY MODEL (CC2420 Radio)
# ============================================================================
ENABLE_ENERGY_MODEL = True  # Enable energy consumption tracking and node shutdown
ENABLE_ENERGY_DEBUG = True  # Enable debug logging for energy consumption
CC2420_DATA_RATE = 250000  # Radio data rate in bits per second (250 kbps)
CC2420_VOLTAGE = 3.0  # Operating voltage in volts
CC2420_PHY_OVERHEAD = 6  # Physical layer overhead in bytes (preamble + SFD + PHR)
CC2420_PLL_OVERHEAD_ENERGY = 10e-6  # PLL turnaround energy overhead in Joules (10 µJ)
TX_POWER_LEVELS = {
    -25: 8.5,  # Current consumption in mA at -25 dBm
    -15: 9.9,  # Current consumption in mA at -15 dBm
    -10: 11.0,  # Current consumption in mA at -10 dBm
    -5: 14.0,  # Current consumption in mA at -5 dBm
    0: 17.4  # Current consumption in mA at 0 dBm (maximum power)
}
TX_POWER_MIN = -25  # Minimum transmission power in dBm
TX_POWER_MAX = 0  # Maximum transmission power in dBm
TX_POWER_DEFAULT = 0  # Default transmission power in dBm
USE_GLOBAL_TX_POWER = False  # If True, all nodes use same TX power; if False, per-cluster power
CC2420_RX_CURRENT = 18.8  # Receive current consumption in mA
BATTERY_VOLTAGE = 3.0  # Battery voltage in volts (two AA alkaline batteries)
BATTERY_CAPACITY = 2000  # Battery capacity in mAh
BATTERY_ENERGY_TOTAL = BATTERY_VOLTAGE * BATTERY_CAPACITY * 3600 / 1000  # Total battery energy in Joules
BATTERY_ENERGY_MIN = BATTERY_ENERGY_TOTAL * 0.01  # Minimum energy threshold (1% of total) for node shutdown
BASELINE_CURRENT = 0.0001  # Baseline current consumption when node is idle/sleeping (100 µA)

# ============================================================================
# CLUSTER OPTIMIZATION
# ============================================================================
ENABLE_CLUSTER_OPTIMIZATION = True  # Enable cluster optimization protocol
CLUSTER_OPTIMIZATION_MODE = 'ENERGY'  # Optimization mode: 'ENERGY' or 'CLUSTERS'
CLUSTER_OPTIMIZATION_INTERVAL = 100  # Time interval between optimization runs (simulation time)
