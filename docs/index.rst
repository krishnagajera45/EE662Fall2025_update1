WSN Protocol Simulation Documentation
=====================================

**EE 662 - Wireless Sensor Networks**

**Cluster-Tree Mesh Ad-Hoc Network**

**Title:** Design and Evaluation of a Self-Organizing Sensor Network Combining Cluster-Tree and Mesh Routing

**Student:** Krishna Gajera

**Red ID:** 132625971

----

Welcome to the comprehensive documentation for the Wireless Sensor Network (WSN) Protocol Simulation project. This documentation covers the design, implementation, configuration, and usage of a cluster-tree mesh ad-hoc network protocol for wireless sensor networks.

.. toctree::
   :maxdepth: 3
   :caption: Contents:

   overview
   protocol_design
   implementation
   configuration
   usage
   api_reference
   analysis

Overview
--------

This simulation implements a comprehensive WSN protocol with the following key features:

* **Neighbor Discovery**: One-hop and multi-hop neighbor discovery with neighbor table sharing
* **Cluster Formation**: Dynamic cluster formation with configurable cluster sizes
* **Routing**: Mesh-first routing with tree fallback for efficient packet delivery
* **Energy Model**: CC2420 radio-based energy consumption tracking
* **Network Recovery**: Node failure and recovery mechanisms
* **Cluster Optimization**: Protocols to minimize clusters or energy consumption
* **Packet Tracing**: Full path recording for data packets
* **Comprehensive Logging**: Detailed CSV logging for analysis

Quick Start
-----------

To run a simulation:

.. code-block:: bash

   python3 wsnlab/data_collection_tree.py

To generate analysis plots:

.. code-block:: bash

   python3 generate_all_plots.py

To run batch simulations (10 runs):

.. code-block:: bash

   python3 run_batch_simulations.py

Key Components
--------------

* :doc:`protocol_design` - Detailed protocol design and architecture
* :doc:`implementation` - Implementation details and code structure
* :doc:`configuration` - Configuration parameters and customization
* :doc:`usage` - Usage guide and examples
* :doc:`api_reference` - API documentation
* :doc:`analysis` - Analysis tools and plotting

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

