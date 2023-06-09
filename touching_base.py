import streamlit as st
import topologicpy
import topologic
from topologicpy.CellComplex import CellComplex
from topologicpy.Cluster import Cluster
from topologicpy.Topology import Topology
from topologicpy.Plotly import Plotly
from topologicpy.Dictionary import Dictionary
import ifcopenshell
import ifcopenshell.geom
import multiprocessing
import uuid
import os.path
import pathlib

st.title('Touching Base')

def adjacency(topologyA, topologyB):
    bbA = Topology.BoundingBox(topologyA)
    bbB = Topology.BoundingBox(topologyB)
    result1 = Topology.Boolean(bbA, bbA, operation="intersect")
    if not result1:
        return "separated"
    result2 = Topology.Boolean(topologyA, topologyB, operation="intersect")
    if not result2:
        return "separated"
    result3 = Topology.Boolean(topologyA, topologyB, operation="merge")
    if isinstance(result3, topologic.CellComplex):
        cells = CellComplex.Cells(result3)
        if len(cells) == 2:
            return "touching"
        elif len(cells) > 2:
            return "overlapping"
    
    result4 = Topology.Boolean(topologyA, topologyB, operation="intersect")
    if not result3:
        return "separated"
    return "overlapping"

def convertToCSVString(csv):
    if not csv:
        return ""
    csv_string = ""
    i = 0
    for i, line in enumerate(csv):
        for item in line:
            csv_string = csv_string+item+","
        if not i == len(csv)-1:
            csv_string = csv_string+"\n"
    return csv_string

def topologiesByIFCFile(ifc_file, transferDictionaries=True):
    topologies = []
    topology = None
    if ifc_file:
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(dir='.', suffix='.ifc') as f:
            f.write(ifc_file.getbuffer())
            ifc_file = ifcopenshell.open(f.name)
        topologies = []
        settings = ifcopenshell.geom.settings()
        settings.set(settings.DISABLE_TRIANGULATION, False)
        settings.set(settings.USE_BREP_DATA, False)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.SEW_SHELLS, True)
        settings.set(settings.INCLUDE_CURVES, False)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, True)
        products = ifc_file.by_type('IfcProduct')
        st.write("Found", str(len(products)), "IFC products")
        if len(products) > 50:
            st.write("WARNING, can only convert a maximum of 50 IFC products")
            products = products[:50]
        text="Converting to Topologies"
        conv_bar = st.progress(0, text=text)
        for i, product in enumerate(products[:50]):
            conv_bar.progress(int(float(i)/float(len(products))*100.0), text=text)
            try:
                shape = ifcopenshell.geom.create_shape(settings, product)
                verts = shape.geometry.verts # X Y Z of vertices in flattened list e.g. [v1x, v1y, v1z, v2x, v2y, v2z, ...]
                faces = shape.geometry.faces # Indices of vertices per triangle face e.g. [f1v1, f1v2, f1v3, f2v1, f2v2, f2v3, ...]
                vertices = [[verts[i], verts[i + 1], verts[i + 2]] for i in range(0, len(verts), 3)]
                faces = [[faces[i], faces[i + 1], faces[i + 2]] for i in range(0, len(faces), 3)]
                topology = Topology.SelfMerge(Topology.ByGeometry(vertices=vertices, faces=faces))
            except:
                topology = None
            if topology:
                if transferDictionaries:
                    keys = []
                    values = []
                    keys.append("TOPOLOGIC_color")
                    values.append([1.0,1.0,1.0,1.0])
                    keys.append("TOPOLOGIC_id")
                    values.append(str(uuid.uuid4()))
                    keys.append("TOPOLOGIC_name")
                    values.append(shape.name)
                    keys.append("TOPOLOGIC_type")
                    values.append(Topology.TypeAsString(topology))
                    keys.append("IFC_id")
                    values.append(str(shape.id))
                    keys.append("IFC_guid")
                    values.append(str(shape.guid))
                    keys.append("IFC_unique_id")
                    values.append(str(shape.unique_id))
                    keys.append("IFC_name")
                    values.append(shape.name)
                    keys.append("IFC_type")
                    values.append(shape.type)
                    d = Dictionary.ByKeysValues(keys, values)
                    topology = Topology.SetDictionary(topology, d)
                topologies.append(topology)
    st.write("Converted", str(len(topologies)), "Topologies")
    return topologies

if 'ifc_file' not in st.session_state:
    st.session_state['ifc_file'] = None
if 'topologies' not in st.session_state:
    st.session_state['topologies'] = None
if 'csv' not in st.session_state:
    st.session_state['csv'] = None
if 'options' not in st.session_state:
    st.session_state['options'] = None

ifc_file = st.session_state['ifc_file']
if not ifc_file:
    ifc_file = st.file_uploader(label="IFC File Uploader", type="ifc", accept_multiple_files=False)
    st.session_state['ifc_file'] = ifc_file
topologies = st.session_state['topologies']
options = []
if ifc_file:
    #topologies = Topology.ByImportedIFC(ifc_file, transferDictionaries=True)
    if not topologies:
        topologies = topologiesByIFCFile(ifc_file, transferDictionaries=True)
        newTopologies = []
        for i, topology in enumerate(topologies):
            d = Topology.Dictionary(topology)
            newTopology = Topology.SelfMerge(topology)
            if not isinstance(newTopology, topologic.Cell):
                cells = Topology.Cells(newTopology)
                if len(cells) > 0:
                    for i, cell in enumerate(cells):
                        name = Dictionary.ValueAtKey(d, "IFC_name")
                        name = name+"_part_"+str(i+1)
                        d2 = Dictionary.SetValueAtKey(d, "IFC_name", name)
                        options.append(name)
                        cell = Topology.SetDictionary(cell, d2)
                        newTopologies.append(cell)
            else:
                newTopology = Topology.SetDictionary(newTopology, d)
                newTopologies.append(newTopology)
        topologies = newTopologies
        st.session_state['topologies'] = topologies
        st.session_state['options'] = options

    csv = st.session_state['csv']
    if not csv:
        with st.form("run_clas_detection"):
            runall = st.checkbox("Detect All Clashes", value=False)
            submitted = st.form_submit_button("Submit")
    if submitted:
        if runall:
            used = []
            text="Preparing Adjacency Matrix"
            adj_bar = st.progress(1, text=text)
            for i in range(len(topologies)):
                adj_bar.progress(int(float(i)/float(len(topologies))*100.0), text=text)
                row = []
                for j in range(len(topologies)):
                    row.append(0)
                used.append(row)

            counter = 1
            csv = []
            condition = "Unknown"
            options = []
            text="Clash Detection"
            clash_bar = st.progress(2, text=text)
            for i in range(len(topologies)):
                clash_bar.progress(int(float(i)/float(len(topologies))*100.0), text=text)
                t_d = Topology.Dictionary(topologies[i])
                t_name = Dictionary.ValueAtKey(t_d,"IFC_name")
                t_id = Dictionary.ValueAtKey(t_d,"IFC_id")
                for j in range(len(topologies)):
                    if used[i][j] == 0 and (not i==j):
                        k_d = Topology.Dictionary(topologies[j])
                        k_name = Dictionary.ValueAtKey(k_d,"IFC_name")
                        k_id = Dictionary.ValueAtKey(k_d,"IFC_id")
                        condition = adjacency(topologies[i], topologies[j])
                        csv.append([str(counter),t_name,k_name,condition])
                        counter = counter + 1
                        used[i][j] = 1
                        used[j][i] = 1
            st.session_state['csv'] = csv
    
    #st.dataframe(data=csv)
    csv_string = convertToCSVString(csv)
    options = st.session_state['options']
    st.download_button("Download CSV", csv_string, "adjacency.csv", "text/csv", key='download-csv')
    with st.form("my_form"):
        optionA = st.selectbox("objectA", options=options, index=0, key=1)
        optionB = st.selectbox("objectB", options=options, index=0, key=2)
        show = st.checkbox("show", value=False)
        isolate = st.checkbox("isolate", value=True)
        submitted2 = st.form_submit_button("Submit")
    if submitted2:
        if (optionA and optionB) and (not optionA == optionB):
            topologyA = topologies[options.index(optionA)]
            d = Topology.Dictionary(topologyA)
            name = Dictionary.ValueAtKey(d, "IFC_name")
            st.write("Topology A: ", name)
            topologyB = topologies[options.index(optionB)]
            d = Topology.Dictionary(topologyB)
            name = Dictionary.ValueAtKey(d, "IFC_name")
            st.write("Topology B: ", name)
            if topologyA and topologyB:
                condition = adjacency(topologyA, topologyB)
                if condition == "touching":
                    st.success(condition, icon="🙏")
                else:
                    st.info(condition, icon="ℹ️")
                if show:
                    if not isolate:
                        cluster = Cluster.ByTopologies(topologies)
                        data00 = Plotly.DataByTopology(cluster, showFaces=False, edgeColor="lightgray", vertexColor="lightgray", edgeLabel="", vertexLabel="", showEdgeLegend=False, showVertexLegend=False)
                    else:
                        data00 = []
                    
                    dataA = Plotly.DataByTopology(topologyA, faceOpacity=1, faceColor="red", showEdges=False, showVertices=False, faceLabel=optionA)
                    dataB = Plotly.DataByTopology(topologyB, faceOpacity=1, faceColor="blue", showEdges=False, showVertices=False, faceLabel=optionB)
                    fig = Plotly.FigureByData(data00+dataA+dataB)
                    st.plotly_chart(fig)
                    if st.button('RESET'):
                        ifc_file = None
                        topologies = None
                        csv = None
                        options = None
                        st.session_state['ifc_file'] = None
                        st.session_state['topologies'] = None
                        st.session_state['csv'] = None
                        st.session_state['options'] = None

        elif optionA == optionB:
            st.write("WARNING: identical object")
