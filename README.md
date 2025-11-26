# WSN Protocol Simulation


## What This Does

The simulation creates a network of sensor nodes that:
- Discover neighbors (one-hop and multi-hop)
- Form clusters with cluster heads
- Route packets using mesh and tree routing
- Handle node failures and recoveries
- Track energy consumption
- Optimize cluster formation

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

### Generating Plots (WORKING ON IT).

After running the simulation, generate all the analysis plots:

```bash
python3 generate_all_plots.py
```

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

- `registration_log.csv` - When each node joined the network
- `packet_delays.csv` - Packet delivery times
- `packet_paths.csv` - Full paths packets took
- `recovery_events.csv` - Node failure and recovery events
- `orphan_events.csv` - Nodes that lost their parent
- `role_changes.csv` - When nodes changed roles
- `clusterhead_distances.csv` - Distances between cluster heads



## Requirements

- Python 3.6+
- matplotlib (for plots)
- numpy (for calculations)

Install missing packages:
```bash
pip install matplotlib numpy
```

## Running Multiple Simulations

Use the batch runner for multiple runs:

```bash
python3 run_batch_simulations.py
```

This runs the simulation 10 times and averages the results.

## Notes

- The visualization window shows nodes as colored dots:
  - White: Undiscovered
  - Yellow: Unregistered (trying to join)
  - Green: Registered
  - Blue: Cluster Head
  - Black: Root node
  - Gray: Failed/Shutdown

- Energy model uses CC2420 radio specifications
- Routing uses mesh-first, tree-fallback strategy
- Cluster optimization can minimize clusters or energy consumption

That's it! 
