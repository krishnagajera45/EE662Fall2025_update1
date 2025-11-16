import math
## network properties
BROADCAST_NET_ADDR = 255
BROADCAST_NODE_ADDR = 255
TOTAL_BITS = 16


## node properties
NODE_DEFAULT_TX_POWER = "0 dBm"  # default transmission power level
TX_POWER_LEVELS = ["-25 dBm", "-15 dBm", "-10 dBm", "-5 dBm", "0 dBm"]  # available power levels
NODE_TX_RANGES = {"-25 dBm": 5, "-15 dBm": 25, "-10 dBm": 50, "-5 dBm": 75, "0 dBm": 100}  # TX range in meters for each power level
NODE_ARRIVAL_MAX = 200  # max time to wake up
NODE_LOSS_CHANCE = 0.05 #percentage points, i.e 0.05 = 5%

## transmission power properties
TX_POWER_MODE = 'UNIFORM'  # 'UNIFORM' for all nodes same power, 'PER_CLUSTER' for cluster-specific power
ALLOW_TX_POWER_CHOICE = 0  # 1 for smart choice (distance-based), 0 for default power level

## Radio properties (CC2420)
DATARATE = 250000  # data rate, 250 kbps
MTU = 127 + 6  # size of the over the air packet (127 bytes + 6 bytes PHY overhead)
VOLTAGE = 3  # volts
TX_CURRENTS = {"-25 dBm": 8.5, "-15 dBm": 9.9, "-10 dBm": 11, "-5 dBm": 14, "0 dBm": 17.4}  # mA
RX_CURRENT = 18.8  # mA


## simulation properties
SIM_NODE_COUNT = 20  # noce count in simulation
SIM_NODE_PLACING_CELL_SIZE = 75  # cell size to place one node
SIM_DURATION = 5000  # simulation Duration in seconds
SIM_TIME_SCALE = 0.001  #  The real time dureation of 1 second simualtion time
SIM_TERRAIN_SIZE = (1400, 1400)  #terrain size
SIM_TITLE = 'Data Collection Tree'  # title of visualization window
SIM_VISUALIZATION = True  # visualization active
SCALE = 1  # scale factor for visualization
VIS = 1 #0 for no viz, 1 for viz
SEED = 1 #seed for reproducibility 
NUM_OF_CHILDREN = 253 
bits_child = math.ceil(math.log2(NUM_OF_CHILDREN))
bits_cluster = TOTAL_BITS - bits_child
NUM_OF_CLUSTERS = (1 << bits_cluster) - 1

## application properties
SLEEP_MODE_PROBE_TIME_INTERVAL = 30
HEART_BEAT_TIME_INTERVAL = 1
JOIN_REQUEST_TIME_INTERVAL = 5
NETWORK_REQUEST_TIME_INTERVAL = JOIN_REQUEST_TIME_INTERVAL * 2
DATA_INTERVAL = 100
MAX_MESH_DISCOVERY_HOPS = 1
NEIGHBOR_INFO_BROADCAST_INTERVAL = 30
REPAIRING_METHOD = 'FIND_ANOTHER_PARENT' # 'ALL_ORPHAN', 'FIND_ANOTHER_PARENT'
EXPORT_CH_CSV_INTERVAL = 10  # simulation time units;
EXPORT_NEIGHBOR_CSV_INTERVAL = 10  # simulation time units;

## failure and recovery properties
ENABLE_NODE_FAILURE = True  # Enable random node failure simulation
NODE_FAILURE_START_TIME = 1000  # Time when first node failure occurs (simulation time)
NODE_FAILURE_INTERVAL = 500  # Interval between node failures (simulation time)
NODE_RECOVERY_TIME = 200  # Time before failed node recovers (simulation time)
NUM_NODES_TO_FAIL = 2  # Number of nodes to randomly fail
NEIGHBOR_TIMEOUT_MULTIPLIER = 3  # Multiplier for heartbeat interval to detect dead neighbors