import math
## network properties
BROADCAST_NET_ADDR = 255
BROADCAST_NODE_ADDR = 255
TOTAL_BITS = 16


## node properties
NODE_TX_RANGE = 100  # transmission range of nodes
NODE_ARRIVAL_MAX = 200  # max time to wake up
NODE_LOSS_CHANCE = 0.0 #percentage points, i.e 10 = 10%


## simulation properties
SIM_NODE_COUNT = 100  # noce count in simulation
SIM_NODE_PLACING_CELL_SIZE = 75  # cell size to place one node
SIM_DURATION = 5000  # simulation Duration in seconds
SIM_TIME_SCALE = 0.001  #  The real time dureation of 1 second simualtion time
SIM_TERRAIN_SIZE = (1400, 1400)  #terrain size
SIM_TITLE = 'Data Collection Tree'  # title of visualization window
SIM_VISUALIZATION = True  # visualization active
SCALE = 1  # scale factor for visualization
VIS = 0 #0 for no viz, 1 for viz
SEED = 1 #seed for reproducibility 
NUM_OF_CHILDREN = 253 #num of children a given cluster head can have, must be 2^N - 3
bits_child = math.ceil(math.log2(NUM_OF_CHILDREN))
bits_cluster = TOTAL_BITS - bits_child
NUM_OF_CLUSTERS = (1 << bits_cluster) - 1

## application properties
SLEEP_MODE_PROBE_TIME_INTERVAL = 30
HEART_BEAT_TIME_INTERVAL = 1
JOIN_REQUEST_TIME_INTERVAL = 5
NETWORK_REQUEST_TIME_INTERVAL = JOIN_REQUEST_TIME_INTERVAL * 2
DATA_INTERVAL = 100
MESH_HOP_N = 1
TABLE_SHARE_INTERVAL = 30
REPAIRING_METHOD = 'FIND_ANOTHER_PARENT' # 'ALL_ORPHAN', 'FIND_ANOTHER_PARENT'
EXPORT_CH_CSV_INTERVAL = 10  # simulation time units;
EXPORT_NEIGHBOR_CSV_INTERVAL = 10  # simulation time units;