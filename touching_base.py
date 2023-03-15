import streamlit as st
import topologicpy
import topologic
from topologicpy.Cell import Cell
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

def convertToCSVString(csv):
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
            st.write(f.name)
            ifc_file = ifcopenshell.open(f.name)
        st.write("IFC File:", ifc_file)
        topologies = []
        settings = ifcopenshell.geom.settings()
        settings.set(settings.DISABLE_TRIANGULATION, False)
        settings.set(settings.USE_BREP_DATA, False)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.SEW_SHELLS, True)
        settings.set(settings.INCLUDE_CURVES, False)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, True)
        products = ifc_file.by_type('IfcProduct')
        st.write("Found Products:", len(products))
        i = 0
        for product in products:
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
    st.write("Found", len(topologies), "Topologies")
    return topologies

ifc_file = st.file_uploader(label="uploader01", type="ifc", accept_multiple_files=False)
if ifc_file:
    #topologies = Topology.ByImportedIFC(ifc_file, transferDictionaries=True)
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
                    cell = Topology.SetDictionary(cell, d2)
                    newTopologies.append(cell)
        else:
            newTopology = Topology.SetDictionary(newTopology, d)
            newTopologies.append(newTopology)

    used = []
    text="Preparing Adjacency Matrix"
    my_bar = st.progress(0, text=text)
    for i in range(len(newTopologies)):
        my_bar.progress(i, text=text)
        row = []
        for j in range(len(newTopologies)):
            row.append(0)
        used.append(row)

    bbList = []
    for topology in newTopologies:
        bbList.append(Topology.BoundingBox(topology))
    counter = 1
    csv = []
    condition = "Unknown"
    options = []
    for i in range(len(newTopologies)):
        t_d = Topology.Dictionary(newTopologies[i])
        t_name = Dictionary.ValueAtKey(t_d,"IFC_name")
        t_id = Dictionary.ValueAtKey(t_d,"IFC_id")
        options.append(t_id)
        for j in range(len(newTopologies)):
            if used[i][j] == 0 and (not i==j):
                k_d = Topology.Dictionary(newTopologies[j])
                k_name = Dictionary.ValueAtKey(k_d,"IFC_name")
                k_id = Dictionary.ValueAtKey(k_d,"IFC_id")
                temp = Topology.Boolean(bbList[i], bbList[j], operation="merge")
                if isinstance(temp, topologic.CellComplex):
                    temp = Topology.Boolean(newTopologies[i], newTopologies[j], operation="merge")
                    if isinstance(temp, topologic.CellComplex):
                        temp_cells = Topology.Cells(temp)
                        if len(temp_cells) == 2:
                            condition = "touching"
                        elif len(temp_cells) > 2:
                            condition = "overlapping"
                    else:
                        condition = "separated"
                else:
                    condition = "separated"
                csv.append([str(counter),t_name,k_name,condition])
                counter = counter + 1
                used[i][j] = 1
                used[j][i] = 1
    #st.dataframe(data=csv)
    csv_string = convertToCSVString(csv)
    st.download_button("Download CSV", csv_string, "adjacency.csv", "text/csv", key='download-csv')
    optionA = st.selectbox("objectA", options=options, index=0, key=1)
    optionB = st.selectbox("objectA", options=options, index=0, key=2)
    if (optionA and optionB) and (not optionA == optionB):
        topologyA = Topology.Filter(topologies, topologyType='cell', searchType='any', key="IFC_id", value=optionA)[0]
        topologyB = Topology.Filter(topologies, topologyType='cell', searchType='any', key="IFC_id", value=optionA)[0]
        temp = Topology.Boolean(newTopologies[i], newTopologies[j], operation="merge")
        condition = "unknown"
        if isinstance(temp, topologic.CellComplex):
            temp_cells = Topology.Cells(temp)
            if len(temp_cells) == 2:
                condition = "touching"
            elif len(temp_cells) > 2:
                condition = "overlapping"
        else:
            condition = "separated"
        st.write(condition)
        data = Plotly.DataByTopology(temp)
        fig = Plotly.FigureByData(data)
        st.plotly_chart(fig, use_container_width=True)
