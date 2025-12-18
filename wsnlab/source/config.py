
import math

## network properties
BROADCAST_NET_ADDR = 255
BROADCAST_NODE_ADDR = 255
TOTAL_BITS = 16  # Total bits for addressing




## node properties
NODE_TX_RANGE = 120  # transmission range of nodes (increase coverage for clustering - need 2x cell size for diagonal neighbors)
NODE_ARRIVAL_MAX = 100  # max time to wake up (reduced for faster network formation)

## cluster formation controls
MAX_CHILD_NODES_ALLOWED_PER_CLUSTER = 20  # Maximum child nodes per cluster (controls cluster size and topology)
bits_child = math.ceil(math.log2(MAX_CHILD_NODES_ALLOWED_PER_CLUSTER))
bits_cluster = TOTAL_BITS - bits_child
NUM_OF_CLUSTERS = (1 << bits_cluster) - 1  # Maximum number of clusters

# Legacy alias for backward compatibility
NUM_OF_CHILDREN = MAX_CHILD_NODES_ALLOWED_PER_CLUSTER


## simulation properties
SIM_NODE_COUNT = 100
SIM_NODE_PLACING_CELL_SIZE = 95  # increased spacing to reduce overlap (was 75)
SIM_DURATION = 3000  # Fig 5
SIM_TIME_SCALE = 0.00001  #  The real time dureation of 1 second simualtion time
SIM_TERRAIN_SIZE = (1200, 1200)  # terrain size
SIM_TITLE = 'Data Collection Tree'  # title of visualization window
SIM_VISUALIZATION = False  # Faster simulation
SCALE = 0.8  # scale factor for visualization
SIM_SEED = 50 # Random seed for reproducible simulations
SIM_BACKGROUND_COLOR = 'white'  # Background color for simulation window: 'white', 'lightgray', '#F0F0F0', etc.


## application properties
HEARTH_BEAT_TIME_INTERVAL = 10  # Reduced from 100 to 10 for faster neighbor discovery
REPAIRING_METHOD = 'FIND_ANOTHER_PARENT' # 'ALL_ORPHAN', 'FIND_ANOTHER_PARENT'
EXPORT_CH_CSV_INTERVAL = 10  # simulation time units;
EXPORT_NEIGHBOR_CSV_INTERVAL = 10  # simulation time units;

## neighbor discovery properties
ENABLE_MULTIHOP_DISCOVERY = True  # Enable multi-hop neighbor discovery
MAX_HOP_DISTANCE = 3
NEIGHBOR_SHARE_INTERVAL = 30  # How often to share neighbor info (simulation time)
ENABLE_NEIGHBOR_DEBUG = True  # Toggle for neighbor discovery debug logs

## routing & debug toggles
ENABLE_LOG_FILE = True  # Write simulation events to a timestamped log
ENABLE_ROUTING_DEBUG = True  # Mesh/tree routing debug statements
ENABLE_CLUSTER_DEBUG = True
ENABLE_MESH_ROUTING = True
ENABLE_TREE_ROUTING = True
# Note: If ENABLE_MESH_ROUTING = False, only tree routing will be used
#       If ENABLE_TREE_ROUTING = False, only mesh routing will be used (may fail if no mesh route)
ENABLE_PACKET_VISUALIZATION = True  # Visualize data packets as they travel through network
PACKET_TRACE_DURATION = 10.0  # How long to keep packet trace lines visible (seconds)

## data traffic properties
DATA_PACKET_INTERVAL = 5  # Fig 5

## channel model / packet loss
PACKET_LOSS_RATE = 0.0001  # Fig 5
ENABLE_PACKET_LOSS_DEBUG = True

## network recovery properties
ENABLE_NODE_FAILURE_RECOVERY = False  # Enable random node failures for testing recovery
NODE_FAILURE_START_TIME = 200  # T1: When to start introducing failures (simulation time)
NODE_FAILURE_INTERVAL = 100  # Time between random node failures
NODE_RECOVERY_TIME_MIN = 50  # Minimum time before node recovers (T2-T3 period)
NODE_RECOVERY_TIME_MAX = 150  # Maximum time before node recovers (T3)
NUM_NODES_TO_FAIL = 0  # No failures for Fig 5
ENABLE_RECOVERY_DEBUG = True  # Toggle for recovery debug logs

## visual highlight properties (for easy snapshot comparison)
FAILURE_HIGHLIGHT_DURATION = 10  # How long to keep failed nodes RED (seconds) - makes T1 snapshots obvious
ORPHAN_HIGHLIGHT_DURATION = 10  # How long to keep orphaned nodes ORANGE (seconds) - makes T1-T2 snapshots obvious

## network snapshot properties (for recovery algorithm testing - class notes methodology)
ENABLE_NETWORK_SNAPSHOTS = False
SNAPSHOT_FOLDER = "snapshots"  # Folder name to store all snapshot PNG files
CAPTURE_SIMULATION_WINDOW = False  # If True, capture actual simulation window (requires PIL/Pillow). If False, use matplotlib visualization
SNAPSHOT_BEFORE_T1 = False  # Take snapshot before T1 (baseline network state)
SNAPSHOT_AT_T1 = False  # Take snapshot at T1 (when failures occur)
SNAPSHOT_T1_T2_AFTER_FAILURE = False  # Take snapshot between T1-T2 (after failure, show orphans)
SNAPSHOT_T1_T2_DELAY = 5  # Delay after T1 to take T1-T2 snapshot (seconds)
SNAPSHOT_T2_T3_RECOVERY = False  # Take snapshot during T2-T3 (recovery in progress)
SNAPSHOT_AT_T3_AFTER_RECOVERY = False  # Take snapshot at T3 (after recovery)
SNAPSHOT_AFTER_T3_INTERVAL = 50  # Interval for snapshots after T3 (seconds)
SNAPSHOT_AFTER_T3_COUNT = 3  # Number of snapshots to take after T3
SNAPSHOT_FINAL_STATE = False  # Take final snapshot at simulation end

## router / CH transfer properties (for overlap reduction)
ENABLE_CH_TRANSFER = True  # Enable CH role transfer to reduce cluster overlap
MIN_MEMBERS_FOR_TRANSFER = 1  # Minimum members before CH can transfer role (allows early transfer to reduce overlap)

## cluster head creation properties
ENABLE_PROACTIVE_CH_CREATION = True  # Allow REGISTERED nodes to proactively become cluster heads (enabled for isolated nodes)
PROACTIVE_CH_TIMER = 60  # Time (seconds) after registration before isolated REGISTERED node can become CH (only if no parent available)
UNREGISTERED_CH_TRIGGER_THRESHOLD = 3  # Number of failed join attempts before UNREGISTERED node triggers CH creation (reduced spam)

## energy model properties (CC2420 radio)
ENABLE_ENERGY_MODEL = True
ENABLE_ENERGY_DEBUG = True

# CC2420 Radio Specifications
CC2420_DATA_RATE = 250000  # bits per second (250 kbps)
CC2420_VOLTAGE = 3.0  # Volts
CC2420_PHY_OVERHEAD = 6  # bytes (4 preamble + 1 SFD + 1 PHR)
CC2420_PLL_OVERHEAD_ENERGY = 10e-6  # Joules (10 µJ for RX/TX PLL turnaround)

# TX Power Levels (dBm) and corresponding currents (mA) for CC2420
TX_POWER_LEVELS = {
    -25: 8.5,   # mA at -25 dBm
    -15: 9.9,   # mA at -15 dBm
    -10: 11.0,  # mA at -10 dBm
    -5: 14.0,   # mA at -5 dBm
    0: 17.4     # mA at 0 dBm (maximum)
}

# TX Power Configuration
TX_POWER_MIN = -25  # Minimum TX power in dBm
TX_POWER_MAX = 0     # Maximum TX power in dBm
TX_POWER_DEFAULT = 0  # Default TX power in dBm (used if per-cluster power not set)
USE_GLOBAL_TX_POWER = False  # If True, all nodes use same TX power; if False, per-cluster power

# RX Current for CC2420
CC2420_RX_CURRENT = 18.8  # mA (receive current)

# Battery Configuration (Two AA Alkaline Batteries)
BATTERY_VOLTAGE = 3.0  # Volts
BATTERY_CAPACITY = 0.013889  # Ah (50J energy budget)
BATTERY_ENERGY_TOTAL = 15.0  # Fig 5: High energy to reach lifetime
BATTERY_ENERGY_MIN = BATTERY_ENERGY_TOTAL * 0.01  # Minimum energy threshold (1% of total) - node shuts down below this

# Baseline Current (when node is idle/sleeping)
BASELINE_CURRENT = 0.0003  # Fig 5: Low baseline

# Cluster Optimization
ENABLE_CLUSTER_OPTIMIZATION = True  # Enable cluster optimization protocol
CLUSTER_OPTIMIZATION_MODE = 'ENERGY'  # 'CLUSTERS' to minimize number of clusters, 'ENERGY' to minimize energy consumption
CLUSTER_OPTIMIZATION_INTERVAL = 100  # How often to run optimization (simulation time)
