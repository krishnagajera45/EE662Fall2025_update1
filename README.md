# Hybrid Cluster-Tree Mesh Wireless Sensor Network Simulation

**EE 662 - Wireless Sensor Networks**  
A discrete-event simulation framework for evaluating hybrid cluster-tree and mesh routing protocols in wireless sensor networks.

## What This Does

The simulation creates a network of sensor nodes that:
- Discover neighbors (one-hop and multi-hop)
- Form clusters with cluster heads
- Route packets using mesh-first, tree-fallback routing
- Handle node failures and recoveries
- Track energy consumption using CC2420 radio model
- Optimize cluster formation and energy balance

## Quick Start

### Running the Simulation

Just run the main simulation file:

```bash
python3 wsnlab/data_collection_tree.py
```

This will:
- Create 100 nodes (configurable in `wsnlab/source/config.py`)
- Run for 5000 seconds of simulation time
- Generate CSV files with results
- Show a visualization window (if enabled)

### Generating Plots

After running the simulation, generate comprehensive analysis plots:

```bash
python3 generate_all_plots.py
```

This generates different plots including join time analysis, packet delivery ratio, energy consumption, network lifetime, connectivity metrics, and routing analysis.

## Changing Settings

All the settings are in `wsnlab/source/config.py`. Open it in any text editor.

**How many nodes?**
```python
SIM_NODE_COUNT = 100  # Change this number
```

**How long to run?**
```python
SIM_DURATION = 5000   # In seconds
```

**How big should clusters be?**
```python
MAX_CHILD_NODES_ALLOWED_PER_CLUSTER = 20  # Max nodes in each cluster
```

**Want to track battery?**
```python
ENABLE_ENERGY_MODEL = True  # Set to False to turn off
```

**Test node failures?**
```python
ENABLE_NODE_FAILURE_RECOVERY = True
NUM_NODES_TO_FAIL = 2        # How many break
NODE_FAILURE_START_TIME = 200  # When they break
```

## Output Files

After running, you'll get these CSV files:

### Network Formation
- `registration_log.csv` - Node join times and registration events
- `role_changes.csv` - Node role transitions (UNDISCOVERED → REGISTERED → CLUSTER_HEAD)

### Packet Routing
- `packet_delays.csv` - End-to-end packet delivery delays
- `packet_paths.csv` - Complete routing paths for each packet
- `packet_routes.csv` - Individual routing decisions with path types

### Network State
- `connectivity_over_time.csv` - Network connectivity metrics over time
- `node_power_levels_over_time.csv` - Energy levels and consumption breakdown

### Failure and Recovery
- `recovery_events.csv` - Node failure and recovery events
- `orphan_events.csv` - Nodes that lost their parent

### Network Topology
- `clusterhead_distances.csv` - Distances between cluster heads
- `neighbor_distances.csv` - Neighbor distance information
- `multihop_neighbor_table.csv` - Multi-hop neighbor table entries



## Requirements

- Python 3.6+
- SimPy (discrete-event simulation framework)
- matplotlib (for plots)
- numpy (for calculations)
- Tkinter (usually included with Python, for visualization)

Install missing packages:
```bash
pip install simpy matplotlib numpy
```

## Running Multiple Simulations

Use the batch runner for multiple runs:

```bash
python3 run_batch_simulations.py
```

This runs the simulation 10 times and generates aggregated statistics in `aggregated_statistics.json`.

## Running Experiments

Individual experiment scripts are available for each figure in the paper:

- `run_fig2_experiment.py` - Join time vs network size
- `run_fig3_experiment.py` - Resilience to node failures
- `run_fig4_experiment.py` - Network lifetime vs energy
- `run_fig5_experiment.py` - Packet delivery under loss
- `run_fig6_experiment.py` - CT+Mesh vs CT-only comparison
- `run_fig7_experiment.py` - Lifetime metrics vs energy
- `run_fig8_experiment.py` - PDR over time
- `run_fig9_experiment.py` - Energy vs traffic
- `run_fig10_experiment.py` - Connectivity vs time
- `run_fig11_experiment.py` - Node lifetime CDF

Each script automatically modifies configuration, runs the simulation, generates the plot, and restores settings.

Example:
```bash
python3 run_fig2_experiment.py
```

## Project Structure

```
.
├── README.md                          # This file
├── COMPE_662_Paper_DETAILED.tex       # LaTeX research paper
├── generate_all_plots.py              # Comprehensive plotting (34+ plots)
├── run_batch_simulations.py           # Batch simulation runner
├── run_fig2_experiment.py             # Experiment scripts (2-11)
├── ...
│
├── wsnlab/                            # Main simulation code
│   ├── data_collection_tree.py        # Core protocol (2938 lines)
│   ├── source/
│   │   ├── config.py                 # Configuration (84+ parameters)
│   │   ├── wsnlab.py                 # Base simulator engine
│   │   └── wsnlab_vis.py             # Visualization layer
│   └── topovis/                       # Topology visualization
│
├── wsnsimpy/                          # Base simulation library
│   ├── wsnsimpy.py                   # Core simulation classes
│   ├── examples/                     # Example protocols
│   └── topovis/                      # Visualization components
│
└── docs/                              # Sphinx documentation
    ├── overview.rst                  # Project overview
    ├── protocol_design.rst           # Protocol details
    └── ...
```

## Protocol Overview

### Node States
Nodes progress through states: **UNDISCOVERED** → **UNREGISTERED** → **REGISTERED** → (optionally) **CLUSTER_HEAD**

### Routing Strategy
- **Mesh-First**: Routes through multi-hop and direct neighbors when available
- **Tree-Fallback**: Hierarchical routing through cluster members, child networks, and parent nodes
- **Path Types**: DIRECT, MESH, MESH_2H, MESH_3H, CLUSTER_MEMBER, TREE_SAME_CLUSTER, TREE_CHILD, TREE_PARENT

### Energy Model
Based on CC2420 radio specifications:
- TX power levels: -25 to 0 dBm (current: 8.5-17.4 mA)
- RX current: 18.8 mA constant
- Baseline current: 0.1 mA (100 µA)
- Initial energy: 21,600 J (2000 mAh × 3.0V)

## Visualization

The visualization window shows nodes as colored dots:
- **White**: Undiscovered
- **Yellow**: Unregistered (trying to join)
- **Green**: Registered
- **Blue**: Cluster Head
- **Black**: ROOT node
- **Red**: Failed/Shutdown
- **Gray**: Orphaned

Real-time visualization shows network topology, node states, energy levels, and packet routing paths.

## Documentation

Comprehensive documentation is available in the `docs/` directory:
- Protocol design details
- Implementation guide
- Configuration reference
- API documentation

Build documentation (requires Sphinx):
```bash
cd docs && make html
```

## Academic Context

This project was developed for **EE 662 - Wireless Sensor Networks** at San Diego State University. The research evaluates hybrid cluster-tree + mesh routing performance across network sizes (25-200 nodes), failure scenarios, packet loss rates, and energy budgets.

**Key Results**:
- 57.1% reduction in disconnected nodes under failures (CT+Mesh vs CT-only)
- Sub-linear scaling of join time (scaling factor ~0.73)
- 100%+ PDR maintained under packet loss rates up to 0.001
- 2.62× energy imbalance between cluster heads and leaf nodes

## Author

**Krishna Gajera**  
Department of Electrical and Computer Engineering  
San Diego State University  
Red ID: 132625971 
