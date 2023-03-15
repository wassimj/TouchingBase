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
        for product in products:
            st.write(product.is_a())
            try:
                shape = ifcopenshell.geom.create_shape(settings, product)
                faces = shape.geometry.faces
                vertices = shape.geometry.verts
                st.write("Faces", len(faces))
                st.write("Vertices", len(vertices))
                topology = Topology.ByGeometry(vertices=vertices, faces=faces)
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
                    values.append(product.name)
                    keys.append("TOPOLOGIC_type")
                    values.append(Topology.TypeAsString(topology))
                    keys.append("IFC_id")
                    values.append(str(product.id))
                    keys.append("IFC_guid")
                    values.append(str(product.guid))
                    keys.append("IFC_unique_id")
                    values.append(str(product.unique_id))
                    keys.append("IFC_name")
                    values.append(product.name)
                    keys.append("IFC_type")
                    values.append(product.type)
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
        st.progress(i, "Transferring Information from IFC to topologicpy")
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
    for i in range(len(newTopologies)):
        st.progress(i, "Preparing Adjacency Matrix")
        row = []
        for j in range(len(newTopologies)):
            row.append(0)
        used.append(row)

    bbList = []
    for topology in newTopologies:
        bbList.append(Topology.BoundingBox(topology))
    counter = 1
    csv = ""

    for i in range(len(newTopologies)):
        st.progress(i, "Detecting Adjacenies")
        t_d = Topology.Dictionary(newTopologies[i])
        t_name = Dictionary.ValueAtKey(t_d,"IFC_name")
        for j in range(len(newTopologies)):
            if used[i][j] == 0 and (not i==j):
                k_d = Topology.Dictionary(newTopologies[j])
                k_name = Dictionary.ValueAtKey(k_d,"IFC_name")
                temp = Topology.Boolean(bbList[i], bbList[j], operation="merge")
                if isinstance(temp, topologic.CellComplex):
                    temp = Topology.Boolean(newTopologies[i], newTopologies[j], operation="merge")
                    if isinstance(temp, topologic.CellComplex):
                        condition = "unknown"
                        temp_cells = Topology.Cells(temp)
                        if len(temp_cells) == 2:
                            condition = "touching"
                        elif len(temp_cells) > 2:
                            condition = "overlapping"
                        csv = csv + str(counter)+","+t_name+","+k_name+","+condition+"\n"
                    else:
                        csv = csv + str(counter)+","+t_name+","+k_name+",separated"+"\n"
                else:
                    csv = csv + str(counter)+","+t_name+","+k_name+",separated"+"\n"
                counter = counter + 1
                used[i][j] = 1
                used[j][i] = 1
    st.write(csv)
