import math

## network properties
BROADCAST_NET_ADDR = 255
BROADCAST_NODE_ADDR = 255
TOTAL_BITS = 16  # Total bits for addressing



## node properties
NODE_TX_RANGE = 100  # transmission range of nodes (increase coverage for clustering)
NODE_ARRIVAL_MAX = 200  # max time to wake up

## cluster formation controls
NUM_OF_CHILDREN = 253  # Maximum nodes per cluster (controls cluster size and topology)
bits_child = math.ceil(math.log2(NUM_OF_CHILDREN))
bits_cluster = TOTAL_BITS - bits_child
NUM_OF_CLUSTERS = (1 << bits_cluster) - 1  # Maximum number of clusters


## simulation properties
SIM_NODE_COUNT = 100  # node count in simulation
SIM_NODE_PLACING_CELL_SIZE = 75  # tighter placement -> better connectivity
SIM_DURATION = 5000  # simulation Duration in seconds
SIM_TIME_SCALE = 0.00001  #  The real time dureation of 1 second simualtion time
SIM_TERRAIN_SIZE = (1400, 1400)  # terrain size
SIM_TITLE = 'Data Collection Tree'  # title of visualization window
SIM_VISUALIZATION = True  # visualization active
SCALE = 1  # scale factor for visualization


## application properties
HEARTH_BEAT_TIME_INTERVAL = 100
REPAIRING_METHOD = 'FIND_ANOTHER_PARENT' # 'ALL_ORPHAN', 'FIND_ANOTHER_PARENT'
EXPORT_CH_CSV_INTERVAL = 10  # simulation time units;
EXPORT_NEIGHBOR_CSV_INTERVAL = 10  # simulation time units;

## neighbor discovery properties
ENABLE_MULTIHOP_DISCOVERY = True  # Enable multi-hop neighbor discovery
MAX_HOP_DISTANCE = 3  # Maximum hop distance to track neighbors
NEIGHBOR_SHARE_INTERVAL = 30  # How often to share neighbor info (simulation time)
ENABLE_NEIGHBOR_DEBUG = True  # Toggle for neighbor discovery debug logs

## routing & debug toggles
ENABLE_LOG_FILE = True  # Write simulation events to a timestamped log
ENABLE_ROUTING_DEBUG = True  # Mesh/tree routing debug statements
ENABLE_CLUSTER_DEBUG = True  # Cluster/member table debug statements
ENABLE_MESH_ROUTING = True  # Try mesh routing first
ENABLE_TREE_ROUTING = True  # Fall back to tree routing

## data traffic properties
DATA_PACKET_INTERVAL = 10  # seconds between random data injections per node