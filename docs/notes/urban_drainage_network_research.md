Hydrodynamic Foundations and the Data Bottleneck in Urban Drainage Modeling
The numerical simulation of urban stormwater routing relies on continuous dynamic wave hydrodynamic modeling1. The standard computational engine used globally for urban drainage simulation is the United States Environmental Protection Agency (EPA) Storm Water Management Model (SWMM)7. SWMM models 1D unsteady flow through closed conduits using the one-dimensional Saint-Venant shallow water equations, which express the conservation of mass and momentum along a pipe link7:


In these governing equations,  represents the cross-sectional flow area,  denotes the volumetric flow rate,  represents time,  represents distance along the conduit axis,  is gravitational acceleration,  is the hydraulic head (water depth plus invert elevation),  is the pipe invert slope, and  represents the friction slope7. The friction slope is computed using Manning's equation for pipe hydraulics:

Where  represents the Manning roughness coefficient of the interior conduit surface (typically ranging from 0.011 for smooth concrete to 0.015 for corrugated metal or aged brick) and  represents the hydraulic radius, defined as the ratio of cross-sectional flow area to wetted perimeter ()5.
Solving these differential equations across a municipal network requires detailed physical parameters for every graph node and edge4. For nodes, models require precise invert elevations above mean sea level, maximum rim elevations (ground surface level), storage areas, and surface ponding capacities4. For edges, models require pipe lengths, cross-sectional shapes (circular, box, or egg-shaped), internal diameters, Manning roughness coefficients, and inlet/outlet invert offsets4.
In practice, acquiring complete spatial datasets containing all these parameters is difficult5. In many small and medium-sized cities, municipal drainage records lack elevation profiles, invert depths, or cross-sectional geometries5. Illegal residential connections, garbage blockage, siltation, and unrecorded construction modifications further cause significant discrepancies between physical reality and administrative records5. Consequently, urban flood nowcasting projects must leverage a combination of open data discovery, synthetic network inversion, and standardized benchmark datasets to construct functional network graphs9.

Synthetic Inversion and Automated Generation Methodologies
When physical municipal mapping is unavailable, researchers apply synthetic generation frameworks to derive functional urban drainage graphs4. Synthetic network generation relies on domain rules: underground stormwater conduits align with surface transportation networks to facilitate maintenance access, and flow directionality is driven by surface topography4.
SWMManywhere is an open-source Python tool developed by Imperial College London that derives synthetic urban drainage network models globally using open geospatial datasets4. The framework executes a multi-stage synthetic inversion workflow:
First, SWMManywhere retrieves OpenStreetMap vector data via the Overpass API to construct surface transportation grids and building footprint polygons4. Topographic terrain elevations are sourced from global Digital Elevation Models (DEMs) such as SRTM or FABDEM4.
Second, road network intersections are mapped as candidate manhole nodes, while road segments are converted into potential pipe links4. Edge directionality is established by enforcing flow along decreasing elevation gradients4. Cyclic loops in the transportation grid are resolved using Minimum Spanning Arborescence (MSA) graph algorithms, transforming the undirected road network into a directed acyclic graph (DAG) terminating at topological surface depressions or river outfall links4.
Third, pipe sizes and hydraulic invert levels are assigned automatically4. The framework calculates the contributing surface catchment area  for each conduit link based on nearby building footprints and impervious surface ratios4. Using the Rational Method, peak design flow  is calculated:

Where  represents the runoff coefficient and  denotes the design rainfall intensity derived from regional intensity-duration-frequency (IDF) curves4. Pipe diameters  and invert slopes  are solved iteratively using Manning's equation under gravity-flow constraints, maintaining minimum self-cleansing velocities () to prevent siltation, and ensuring adequate soil cover depth above pipe crowns4.
Other open-source generation tools include SewerTris, a Python library that constructs synthetic urban layouts and sanitary sewer networks based on parametric spatial distributions41, and Agentic SWMM (aiswmm), an automated workflow platform that integrates QGIS preprocessing, SWMManywhere synthesis, deterministic SWMM execution, and verification provenance tracking42.


Mathematical Formulations and Structural Schema for Drainage Graphs
To process urban drainage infrastructure within machine learning frameworks like PyTorch Geometric or graph analytics platforms like NetworkX, physical parameters must be structured into an attributed directed graph 8. The graph topology consists of a node set  representing point structures, an edge set  representing conduit links, and a weight matrix  encoding spatial and hydraulic properties4.
Node attributes are formalized as a continuous feature vector , where  represents the number of node features8. Node parameters include invert elevation , rim elevation , maximum physical depth , ponding surface area , instantaneous water depth , and localized surface runoff inflow 4.
Edge attributes are formalized as a feature vector , where  denotes conduit features8. Link parameters include pipe length , cross-sectional diameter , Manning roughness coefficient , invert slope , instantaneous flow rate , and flow velocity 4.
Network topology is encoded using an Adjacency Matrix , where  indicates a directed pipe connection from node  to node , and  indicates no connection8. Alternatively, flow directionality can be represented via an Incidence Matrix , defined as:

This mathematical schema enables direct conversion between hydrodynamic differential engines and spatial-temporal graph neural networks7.

Element Type
Hydro-Infrastructure Component
Attribute Name
Variable Notation
Physical Unit
Mathematical / Hydrodynamic Role
Node ()
Manhole / Junction
Invert Elevation

Meters ()
Base datum elevation above mean sea level4




Rim Elevation

Meters ()
Ground surface elevation; threshold for street overflow4




Max Depth

Meters ()
Height from invert to ground level ()7




Surface Area

Square Meters ()
Surface area for localized water ponding when surcharged4




Instantaneous Head

Meters ()
Dynamic hydraulic head ()7
Edge ()
Pipe / Conduit
Length

Meters ()
Physical conduit length between junction centers4




Diameter / Height

Meters ()
Internal geometric cross-section clearance4




Manning Roughness


Internal wall friction factor7




Invert Slope

Dimensionless ()
Longitudinal bed slope driving gravity flow4




Full Flow Capacity


Maximum gravity conveyance capacity before pressurization4


Software Ecosystem and Programmatic Graph Extraction
Constructing, manipulating, and extracting graph objects from urban drainage models requires an integrated Python ecosystem19. Specialized open-source libraries parse structured EPA SWMM files (.inp), run hydrodynamic simulations, extract output binary files (.out), and convert network topologies directly into graph data structures7.
The library swmm_api provides high-level programmatic interfaces for reading, editing, and writing SWMM input files20. It includes macros for structural network manipulation, automated GIS exports, and direct conversion of SWMM network entities into NetworkX directed graph objects20. swmmio offers similar functionality, enabling visualization and Pandas DataFrame representations of model nodes and links36.
For dynamic runtime interaction, PySWMM provides C-API Python bindings to the SWMM 5 computational engine36. PySWMM allows developers to inspect node depths, alter orifice/pump gate openings, and extract instantaneous flow vectors at individual time steps during a live simulation run36.
The following Python script demonstrates the programmatic extraction of an attributed NetworkX directed graph directly from a standard EPA SWMM .inp file using swmm_api:



Python
import networkx as nx
from swmm_api import read_inp_file
from swmm_api.input_file.section_labels import JUNCTIONS, CONDUITS, XSECTIONS, COORDINATES

def extract_drainage_graph(inp_path):
    inp = read_inp_file(inp_path)
    G = nx.DiGraph()
    
    # Process Junction Nodes
    if JUNCTIONS in inp:
        for node_id, junc in inp[JUNCTIONS].items():
            x_coord = inp[COORDINATES][node_id].x if COORDINATES in inp and node_id in inp[COORDINATES] else 0.0
            y_coord = inp[COORDINATES][node_id].y if COORDINATES in inp and node_id in inp[COORDINATES] else 0.0
            
            G.add_node(
                node_id,
                elevation=float(junc.elevation),
                max_depth=float(junc.max_depth),
                pos=(x_coord, y_coord),
                node_type="Junction"
            )
            
    # Process Conduit Links
    if CONDUITS in inp:
        for conduit_id, cond in inp[CONDUITS].items():
            u = cond.from_node
            v = cond.to_node
            
            # Extract Cross-sectional geometry
            geom_1 = 0.0
            if XSECTIONS in inp and conduit_id in inp[XSECTIONS]:
                geom_1 = float(inp[XSECTIONS][conduit_id].geom_1)
                
            u_elev = G.nodes[u]['elevation'] if u in G.nodes else 0.0
            v_elev = G.nodes[v]['elevation'] if v in G.nodes else 0.0
            length = float(cond.length)
            slope = (u_elev - v_elev) / length if length > 0 else 0.0
            
            G.add_edge(
                u,
                v,
                key=conduit_id,
                length=length,
                roughness=float(cond.roughness),
                diameter=geom_1,
                slope=slope
            )
            
    return G

# Execution Example
graph = extract_drainage_graph("tecnopolo_r1.inp")
print(f"Extracted Graph: {graph.number_of_nodes()} Nodes, {graph.number_of_edges()} Edges")


Applied Implementation Pipeline for Hackathon Projects
For engineering teams participating in the Smart India Hackathon or developing urban flood early warning applications, executing a complete project requires a structured, multi-phase operational pipeline10. This pipeline connects initial spatial data acquisition with synthetic network inversion, hydrodynamic engine execution, and spatial-temporal graph neural network modeling7.
Phase 1: Spatial Boundary Ingestion and Surface Mapping
The implementation begins by defining the geographical bounding box (in WGS84 coordinates) of the target urban study area (e.g., a flood-prone municipal ward in Chennai or Mumbai)1. Vector road networks, building footprints, and surface watercourses are extracted automatically from OpenStreetMap via OSMnx19. Digital Elevation Models (DEMs) are acquired from 30m SRTM or FABDEM rasters to establish surface slopes and terrain contours4.
Phase 2: Synthetic Network Synthesis via SWMManywhere
The extracted geospatial layers are passed into SWMManywhere19. The framework processes transportation intersections into junction nodes, aligns pipe links beneath street segments, applies minimum spanning arborescence algorithms to enforce gravity flow toward natural surface outfalls, dimensions pipe diameters using local rainfall IDF curves, and exports a valid EPA SWMM .inp file4.
Phase 3: Hydrodynamic Simulation and Synthetic Training Generation
The derived .inp file is executed using swmm_api or PySWMM under synthetic precipitation scenarios (e.g., 2-year, 10-year, and 50-year return period design storms)9. The simulation runs 1D Saint-Venant dynamic wave routing, outputting time-series node water depths , manhole flooding volumes , and conduit flow rates  at 5-minute intervals7.
Phase 4: Spatial-Temporal Graph Neural Network Training
The network graph and hydrodynamic simulation outputs are converted into PyTorch Geometric format8. Node feature matrices incorporate ground elevations, pipe connectivity, and instantaneous rainfall inputs8. A Spatial-Temporal Graph Neural Network (ST-GNN)—such as a Graph Convolutional Network (GCN) coupled with a Temporal Convolutional Layer—is trained using the 1D SWMM simulation results as ground truth8. The trained GNN acts as a high-speed surrogate model, predicting surcharged nodes and surface flooding in milliseconds7.
Phase 5: Real-Time Coupling and Inundation Dashboard Integration
The trained ST-GNN is integrated with real-time precipitation forecast feeds, such as INSAT-3D/3DR satellite precipitation estimates or regional Doppler weather radar nowcasts11. Predicted node overflow volumes are mapped onto surface Digital Terrain Models (DTMs) using QGIS or Mapbox GL JavaScript interfaces, producing dynamic, location-specific urban inundation maps and automated alerts for disaster management agencies1.
Synthesis and Strategic Outlook
Developing urban drainage network graphs for smart city applications requires bridging the gap between unavailable physical infrastructure records and the data requirements of hydro-informatics models5. While municipal GIS layers in developing regions frequently lack underground pipe invert levels and geometric attributes, open data platforms, global benchmark repositories, and synthetic network generation tools provide viable pathways for graph construction9.
By leveraging synthetic generation tools like SWMManywhere alongside benchmark repositories such as Zenodo Tecnopolo and CITEEC, project teams can construct hydraulically consistent urban drainage graphs for any target municipality4. Converting these spatial networks into attributed directed graphs via Python libraries like swmm_api enables the application of spatial-temporal graph neural networks8. This integrated approach provides a reliable framework for building real-time urban flood nowcasting systems, advancing urban hydrological modeling and disaster resilience1.
