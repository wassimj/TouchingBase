import streamlit as st
import topologicpy
import topologic
from topologicpy.Cell import Cell
from topologicpy.Topology import Topology
from topologicpy.Plotly import Plotly
from topologicpy.Dictionary import Dictionary

st.title('Touching Base')


ifc_file = st.file_uploader("", type="ifc", accept_multiple_files=False)
if ifc_file:
    topologies = Topology.ByImportedIFC(ifc_file, transferDictionaries=True)
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
