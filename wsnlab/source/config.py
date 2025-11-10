## network properties
BROADCAST_NET_ADDR = 255
BROADCAST_NODE_ADDR = 255



## node properties
NODE_TX_RANGE = 100  # transmission range of nodes
NODE_ARRIVAL_MAX = 200  # max time to wake up


## simulation properties
SIM_NODE_COUNT = 100  # noce count in simulation
SIM_NODE_PLACING_CELL_SIZE = 75  # cell size to place one node
SIM_DURATION = 5000  # simulation Duration in seconds
SIM_TIME_SCALE = 0.00001  #  The real time dureation of 1 second simualtion time
SIM_TERRAIN_SIZE = (1400, 1400)  #terrain size
SIM_TITLE = 'Data Collection Tree'  # title of visualization window
SIM_VISUALIZATION = True  # visualization active
SCALE = 0.8  # scale factor for visualization


## application properties
HEARTH_BEAT_TIME_INTERVAL = 100
REPAIRING_METHOD = 'FIND_ANOTHER_PARENT' # 'ALL_ORPHAN', 'FIND_ANOTHER_PARENT'
EXPORT_CH_CSV_INTERVAL = 10  # simulation time units;
EXPORT_NEIGHBOR_CSV_INTERVAL = 10  # simulation time units;

# #KG-Debugging controls (optional)
# If True, neighbor/multihop tables will be printed to DEBUG_LOG_PATH
DEBUG = True
DEBUG_LOG_PATH = 'wsn_debug.log'

# --- optional per-hop delay model (off by default) ---
ENABLE_DELAY_MODEL = True     # set True to enable
PROC_DELAY_MEAN = 0.5          # processing time at a node (sim time units)
TX_DELAY_PER_HOP = 0.3         # transmission time per hop
TX_DELAY_JITTER = 0.2          # +/- jitter added to total