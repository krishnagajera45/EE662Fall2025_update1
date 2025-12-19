Analysis and Plotting
=====================

This document describes the analysis tools and plotting capabilities available for analyzing simulation results.

Available Plots
---------------

The plotting system generates 34 different analysis plots covering all aspects of the protocol. These are organized into several categories:

**Paper Figures (Fig. 2-11)**: Required plots for research paper/report
**General Analysis Plots**: Comprehensive analysis and debugging plots
**CT vs MT Comparison Plots**: Cluster-Tree vs Mesh-Tree routing comparisons
**Energy Analysis Plots**: Energy consumption and lifetime analysis
**Network Performance Plots**: Join time, connectivity, and packet delivery analysis

Paper Figures (Fig. 2-11)
-------------------------

These are the primary plots required for the research paper/report:

Fig. 2: Average Join Time vs Network Size
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_fig2_avg_join_time_vs_network_size()``
**File**: ``fig2_avg_join_time_vs_network_size.png``

Shows average join time as network size increases. Useful for scalability analysis.

Fig. 3: Nodes Killed vs Disconnected
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_fig3_nodes_killed_vs_disconnected()``
**File**: ``fig3_nodes_killed_vs_disconnected.png``

Compares CT (Cluster-Tree) vs MT (Mesh-Tree) routing when nodes are killed. Shows how many nodes become disconnected.

**Alternative**: ``plot_fig3b_nodes_killed_vs_disconnected_bar()`` - Bar chart version

Fig. 4: Network Lifetime vs Initial Energy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_fig4_network_lifetime_vs_initial_energy()``
**File**: ``fig4_network_lifetime_vs_initial_energy.png``

Shows network lifetime for different initial energy levels and traffic loads.

Fig. 5: Packets Sent vs Delivered
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_fig5_packets_sent_vs_delivered()``
**File**: ``fig5_packets_sent_vs_delivered.png``

Shows packet delivery performance for different packet loss rates.

Fig. 6: CT+Mesh vs CT Only
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_fig6_ct_mesh_vs_ct_only()``
**File**: ``fig6_ct_mesh_vs_ct_only.png``

Compares Cluster-Tree with Mesh routing vs Cluster-Tree only routing.

**Alternative**: ``plot_fig6_network_lifetime()`` - Network lifetime comparison

Fig. 7: Energy Impact on Lifetime Metrics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_fig7_energy_impact_on_lifetime_metrics()``
**File**: ``fig7_energy_impact_on_lifetime_metrics.png``

Shows impact of initial energy on lifetime metrics (bar chart).

**Alternative**: ``plot_fig7_avg_energy_ct_comparison()`` - Average remaining energy over time (CT+Mesh vs CT-only)

Fig. 8: PDR Over Time
~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_fig8_pdr_over_time()``
**File**: ``fig8_pdr_over_time.png``

Shows Packet Delivery Ratio (PDR) over time with multiple scenarios.

**Alternative**: ``plot_fig8_network_lifetime_vs_initial_energy()`` - Network lifetime vs initial energy

Fig. 9: Avg Remaining Energy Over Time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_fig9_avg_remaining_energy_over_time()``
**File**: ``fig9_avg_remaining_energy_over_time.png``

Shows average remaining energy over time for different traffic loads.

Fig. 10: Fraction Connected Nodes Over Time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_fig10_fraction_connected_nodes_over_time()``
**File**: ``fig10_fraction_connected_nodes_over_time.png``

Shows fraction of connected nodes over time for different traffic loads.

Fig. 11: CDF of Node Lifetimes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_fig11_cdf_node_lifetimes()``
**File**: ``fig11_cdf_node_lifetimes.png``

Shows Cumulative Distribution Function of node lifetimes for cluster heads vs leaf nodes.

General Analysis Plots
-----------------------

These plots provide comprehensive analysis for debugging and understanding protocol behavior:

Join Time Analysis
~~~~~~~~~~~~~~~~~~

**File**: ``join_time_analysis.png``

Shows:
* Distribution histogram of join times
* Cumulative Distribution Function (CDF)
* Join time vs node registration order
* Box plot with statistics

Useful for:
* Understanding network formation speed
* Identifying nodes with long join times
* Analyzing join time distribution

Cluster Analysis
~~~~~~~~~~~~~~~~

**Function**: ``plot_cluster_analysis()``
**File**: ``cluster_analysis.png``

Shows:
* Cluster size distribution
* Max cluster size vs number of clusters
* Individual cluster sizes
* Cluster statistics summary

Useful for:
* Understanding cluster formation
* Analyzing cluster size distribution
* Optimizing cluster configuration

TX Power Analysis
~~~~~~~~~~~~~~~~~

**File**: ``tx_power_analysis.png``

Shows:
* TX power vs current consumption (CC2420)
* Available TX power levels
* Energy per packet vs TX power
* TX power configuration summary

Useful for:
* Understanding energy consumption
* Selecting optimal TX power levels
* Analyzing energy efficiency

Network Lifetime
~~~~~~~~~~~~~~~~

**Function**: ``plot_network_lifetime()``
**File**: ``network_lifetime.png``

Shows:
* Network lifetime vs packet size (different TX powers)
* Energy consumption per packet
* Network lifetime vs packet rate
* Theoretical lifetime calculations

Useful for:
* Estimating network lifetime
* Understanding packet size impact
* Optimizing packet rate

Packet Tracing
~~~~~~~~~~~~~~

**File**: ``packet_tracing.png``

Shows:
* Network topology with packet traces
* Hop count distribution
* Delay vs hop count correlation
* Packet tracing statistics

Useful for:
* Visualizing packet paths
* Understanding routing efficiency
* Analyzing hop count distribution

Protocol Metrics
~~~~~~~~~~~~~~~~

**Function**: ``plot_protocol_metrics()``
**File**: ``protocol_metrics.png``

Comprehensive dashboard showing:
* Join time distribution
* Packet delay distribution (base and total)
* Role changes over time
* Role transition frequencies
* Recovery performance
* Cluster formation
* Orphan events
* Overall performance summary

Useful for:
* Overall protocol performance assessment
* Identifying bottlenecks
* Comparing different configurations

Batch Simulation Averages
~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_batch_simulation_averages()``
**File**: ``batch_simulation_averages.png``

Shows average statistics from 10 simulation runs:
* Average join time (with error bars)
* Average packet delay
* Average number of clusters
* Summary statistics

Useful for:
* Getting reliable statistics
* Understanding variance
* Reporting average performance

Packet Loss Analysis
~~~~~~~~~~~~~~~~~~~~

**File**: ``packet_loss_vs_join_time.png``

Shows:
* Average join time vs packet loss rate
* Min-max range for join times
* Comparison across loss rates

Useful for:
* Understanding packet loss impact
* Network resilience analysis
* Optimizing for lossy channels

Config Parameters Over Time
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_config_parameters_over_time()``
**File**: ``config_parameters_over_time.png``

Shows network behavior over simulation time:
* Average join time over time
* Role changes over time
* Packet delays over time
* Cumulative nodes joined (network growth)

Useful for:
* Understanding network evolution
* Identifying time-dependent behaviors
* Analyzing network growth patterns

Max Nodes vs Clusters
~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_max_nodes_vs_clusters()``
**File**: ``max_nodes_vs_clusters.png``

Shows:
* Theoretical relationship between max cluster size and cluster count
* Current configuration point
* Actual cluster count from simulation
* Inverse relationship

Useful for:
* Understanding cluster size trade-offs
* Optimizing cluster configuration
* Predicting cluster count

TX Power vs Network Lifetime
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**File**: ``tx_power_vs_network_lifetime.png``

Shows:
* TX power vs energy per packet
* TX power vs network lifetime (different packet sizes)
* Energy efficiency (packets per Joule)
* Current consumption comparison

Useful for:
* Optimizing TX power selection
* Understanding energy-lifetime trade-offs
* Analyzing energy efficiency

Packet Size vs Network Lifetime
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_packet_size_vs_network_lifetime()``
**File**: ``packet_size_vs_network_lifetime.png``

Shows:
* Network lifetime vs packet size (different TX powers)
* Energy consumption vs packet size
* Total packets transmittable vs packet size
* Summary statistics

Useful for:
* Optimizing packet size
* Understanding size-lifetime trade-offs
* Estimating network capacity

Configuration Parameters Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_config_parameters()``
**File**: ``config_parameters.png``

Shows configuration parameter analysis and their impact on network behavior.

CT vs MT Comparison Plots
--------------------------

These plots compare Cluster-Tree (CT) vs Mesh-Tree (MT) routing strategies. The CT+Mesh approach combines the hierarchical structure of cluster-tree routing with the flexibility of mesh routing for improved network performance, reliability, and energy efficiency.

Network Discovery Rate
~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_network_discovery_rate()``
**File**: ``network_discovery_rate.png``

Shows network discovery/registration rate comparison between CT and MT routing. This plot demonstrates how quickly nodes discover and register with the network under different routing strategies. The CT+Mesh approach typically shows improved discovery rates due to multiple routing paths and neighbor sharing mechanisms.

**Key Metrics:**
* Number of nodes discovered over time
* Registration rate (nodes/second)
* Comparison between CT-only and CT+Mesh approaches
* Impact of routing strategy on network formation speed

Packet Delivery with Loss
~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_packet_delivery_with_loss()``
**File**: ``packet_delivery_with_loss.png``

Shows packet delivery performance with packet loss for CT vs MT comparison. This analysis evaluates how the routing strategy handles packet loss scenarios, demonstrating the resilience of the CT+Mesh approach when facing unreliable communication channels.

**Key Metrics:**
* Packet Delivery Ratio (PDR) under different loss rates
* Comparison of CT-only vs CT+Mesh performance
* Impact of packet loss on delivery success
* Network resilience analysis

Registration Time vs Packet Loss
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_registration_time_vs_packet_loss()``
**File**: ``registration_time_vs_packet_loss.png``

Shows node registration time vs packet loss rate for CT vs MT. This plot analyzes how packet loss affects the time required for nodes to successfully join the network, comparing the robustness of different routing approaches.

**Key Metrics:**
* Average registration time at different packet loss rates
* Minimum and maximum registration times
* Standard deviation showing consistency
* Comparison between routing strategies

Packet Delivery Time vs Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_packet_delivery_time_vs_nodes()``
**File**: ``packet_delivery_time_vs_nodes.png``

Shows average time to deliver a packet vs number of nodes (CT vs MT). This analysis evaluates scalability by measuring how packet delivery time changes as the network size increases, demonstrating the efficiency of the CT+Mesh routing approach.

**Key Metrics:**
* End-to-end packet delivery time
* Scalability analysis (performance vs network size)
* Comparison of routing efficiency
* Impact of network size on routing performance

Energy vs Nodes
~~~~~~~~~~~~~~~

**Function**: ``plot_energy_vs_nodes()``
**File**: ``energy_vs_nodes.png``

Shows average energy consumption vs number of nodes (CT vs MT). This plot analyzes energy efficiency by comparing total energy consumption across different network sizes, demonstrating how the CT+Mesh approach balances routing efficiency with energy conservation.

**Key Metrics:**
* Average energy consumption per node
* Total network energy consumption
* Energy efficiency comparison
* Impact of network size on energy usage

Total Energy vs Time
~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_total_energy_vs_time()``
**File**: ``total_energy_vs_time.png``

Shows total system energy over time for CT vs MT comparison. This analysis tracks energy consumption throughout the simulation, providing insights into how routing strategies affect long-term network energy usage and lifetime.

**Key Metrics:**
* Total network energy consumption over time
* Energy consumption rate (Joules/second)
* Network lifetime estimation
* Energy efficiency trends

Recovery Analysis Plots
-----------------------

Nodes Discovered vs Killed
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Function**: ``plot_nodes_discovered_vs_killed()``
**File**: ``nodes_discovered_vs_killed.png``

Shows number of nodes discovered vs number of nodes killed (recovery analysis).

Complete Plot List
------------------

All 34 plotting functions available:

**Paper Figures (11 plots):**
1. ``plot_fig2_avg_join_time_vs_network_size()`` - Fig. 2
2. ``plot_fig3_nodes_killed_vs_disconnected()`` - Fig. 3
3. ``plot_fig3b_nodes_killed_vs_disconnected_bar()`` - Fig. 3 (alt)
4. ``plot_fig4_network_lifetime_vs_initial_energy()`` - Fig. 4
5. ``plot_fig5_packets_sent_vs_delivered()`` - Fig. 5
6. ``plot_fig6_ct_mesh_vs_ct_only()`` - Fig. 6
7. ``plot_fig6_network_lifetime()`` - Fig. 6 (alt)
8. ``plot_fig7_energy_impact_on_lifetime_metrics()`` - Fig. 7
9. ``plot_fig7_avg_energy_ct_comparison()`` - Fig. 7 (alt)
10. ``plot_fig8_pdr_over_time()`` - Fig. 8
11. ``plot_fig8_network_lifetime_vs_initial_energy()`` - Fig. 8 (alt)
12. ``plot_fig9_avg_remaining_energy_over_time()`` - Fig. 9
13. ``plot_fig10_fraction_connected_nodes_over_time()`` - Fig. 10
14. ``plot_fig11_cdf_node_lifetimes()`` - Fig. 11

**General Analysis (12 plots):**
15. ``plot_join_time_analysis()``
16. ``plot_cluster_analysis()``
17. ``plot_tx_power_analysis()``
18. ``plot_network_lifetime()``
19. ``plot_packet_tracing()``
20. ``plot_protocol_metrics()``
21. ``plot_config_parameters()``
22. ``plot_batch_simulation_averages()``
23. ``plot_packet_loss_vs_join_time()``
24. ``plot_config_parameters_over_time()``
25. ``plot_max_nodes_vs_clusters()``
26. ``plot_tx_power_vs_network_lifetime()``
27. ``plot_packet_size_vs_network_lifetime()``

**CT vs MT Comparison (6 plots):**
28. ``plot_network_discovery_rate()``
29. ``plot_packet_delivery_with_loss()``
30. ``plot_registration_time_vs_packet_loss()``
31. ``plot_packet_delivery_time_vs_nodes()``
32. ``plot_energy_vs_nodes()``
33. ``plot_total_energy_vs_time()``

**Recovery Analysis (1 plot):**
34. ``plot_nodes_discovered_vs_killed()``

Generating Plots
----------------

To generate all paper figures (Fig. 2-11):

.. code-block:: bash

   python3 generate_all_plots.py

This will generate all 11 required paper figures. Individual plots can be generated by importing and calling the functions directly:

.. code-block:: python

   from generate_all_plots import plot_fig2_avg_join_time_vs_network_size
   plot_fig2_avg_join_time_vs_network_size()

Command-line options are also available:

.. code-block:: bash

   python3 generate_all_plots.py --fig8  # Generate Fig. 8 only
   python3 generate_all_plots.py --fig5  # Generate Fig. 5 only
   python3 generate_all_plots.py --fig6  # Generate Fig. 6 only
   python3 generate_all_plots.py --fig7  # Generate Fig. 7 only

Interpreting Results
--------------------

Join Time Analysis
~~~~~~~~~~~~~~~~~~

**Good Performance**:
* Mean join time < 50 seconds
* Most nodes join within 100 seconds
* Low variance (consistent join times)

**Poor Performance**:
* Mean join time > 100 seconds
* Many nodes take > 200 seconds
* High variance (inconsistent)

**Improvements**:
* Increase TX range
* Decrease heartbeat interval
* Enable proactive CH creation

Cluster Analysis
~~~~~~~~~~~~~~~~

**Good Configuration**:
* Clusters are reasonably balanced (similar sizes)
* Number of clusters is appropriate for network size
* No extremely large or small clusters

**Poor Configuration**:
* Very uneven cluster sizes
* Too many small clusters (inefficient)
* Too few large clusters (overloaded)

**Optimization**:
* Adjust MAX_CHILD_NODES_ALLOWED_PER_CLUSTER
* Enable CH transfer to balance clusters
* Tune cluster formation parameters

Energy Analysis
~~~~~~~~~~~~~~~

**Efficient Network**:
* Low energy per packet
* Long network lifetime
* Balanced TX/RX energy consumption

**Inefficient Network**:
* High energy per packet
* Short network lifetime
* Excessive TX energy (high power, frequent packets)

**Optimization**:
* Lower TX power (if connectivity allows)
* Reduce packet rate
* Optimize packet size
* Enable energy optimization mode

Routing Analysis
~~~~~~~~~~~~~~~~

**Efficient Routing**:
* Low average hop count
* Short packet delays
* Direct paths when possible

**Inefficient Routing**:
* High hop counts
* Long delays
* Many detours

**Improvements**:
* Improve neighbor discovery
* Optimize routing decisions
* Increase TX range for better connectivity

Recovery Analysis
~~~~~~~~~~~~~~~~~

**Good Recovery**:
* Short recovery times
* Few orphan nodes
* Quick network stabilization

**Poor Recovery**:
* Long recovery times
* Many orphan nodes
* Network instability

**Improvements**:
* Faster heartbeat intervals
* Better orphan detection
* Improved rejoin mechanisms

Report Writing
--------------

When writing reports, you can reference the plots and statistics:

Join Time Report
~~~~~~~~~~~~~~~~

Example text:

"The network was simulated 10 times, and on average, nodes took XX.XX seconds to join the network (standard deviation: XX.XX seconds). The join time distribution shows that 90% of nodes joined within XX seconds, indicating efficient network formation."

Packet Loss Impact
~~~~~~~~~~~~~~~~~~

Example text:

"Packet loss ratio was varied from 0 to 10^-3, and its effect on join time is shown in Figure X. As packet loss increases, the average join time increases from XX seconds to XX seconds, demonstrating the protocol's resilience to packet loss."

Energy Efficiency
~~~~~~~~~~~~~~~~~

Example text:

"TX power analysis shows that lower power levels extend network lifetime but may reduce reliability. At 0 dBm TX power, the network lifetime is estimated at XX hours for 50-byte packets, while at -15 dBm, the lifetime increases to XX hours."

Cluster Optimization
~~~~~~~~~~~~~~~~~~~~

Example text:

"The cluster optimization protocol successfully reduced energy consumption by XX% by adjusting TX power levels based on cluster characteristics. Smaller clusters use lower TX power, resulting in overall energy savings."

Best Practices
--------------

1. **Run Multiple Simulations**: Use batch simulations for reliable statistics
2. **Compare Configurations**: Run with different configs and compare plots
3. **Check CSV Files**: Verify data in CSV files matches plots
4. **Document Parameters**: Note configuration used for each plot
5. **Analyze Trends**: Look for trends across different scenarios
6. **Validate Results**: Check that results make physical sense

Common Analysis Tasks
----------------------

Finding Optimal Cluster Size
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Run simulations with different ``MAX_CHILD_NODES_ALLOWED_PER_CLUSTER`` values
2. Generate ``max_nodes_vs_clusters.png`` plots for each
3. Compare cluster counts and sizes
4. Select configuration that balances cluster count and size

Analyzing Energy Consumption
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Enable energy model and debug logging
2. Run simulation and check log file
3. Generate energy-related plots
4. Analyze:
   * Energy per packet
   * Total energy consumption
   * Energy breakdown (TX/RX/baseline)
   * Network lifetime estimates

Testing Network Resilience
~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Enable node failure recovery
2. Run simulation with failures
3. Generate recovery plots
4. Analyze:
   * Recovery times
   * Orphan node counts
   * Network stability
   * Role changes during recovery

Optimizing TX Power
~~~~~~~~~~~~~~~~~~~

1. Run simulations with different TX power levels
2. Generate ``tx_power_vs_network_lifetime.png``
3. Analyze:
   * Energy consumption
   * Network lifetime
   * Connectivity (packet delivery rate)
4. Select optimal power level

