"""
El siguiente ejemplo ejecuta un escenario de una fuga en una tuberia
a cada tuberría se le asigna una probabilidad de fuga con respecto a cada
metrica de resilencia topografica.
Se eleige la tuberia que es atacada
De manera aleatoria se elige la duracion (p.e. 3.5 hrs) y tiempo (5pm hasta 8:30pm)
Se simula la fuga
Se calcula:
    - la disponinibilidad de servicio de agua en cada nodo
    - Nivel de agua en los tanques
"""
import numpy as np
import matplotlib.pyplot as plt
import pickle
import wntr
import networkx as nx

# Crear el modelo de la red de agua
num_fugas = 1 # numero de fugas simultaneas
inp_file = 'nets_examples/Chihuahua.inp'
wn = wntr.network.WaterNetworkModel(inp_file)

# Configura el modelo de simulacion
duracion = 48*3600 #en segundos (2 dias)
intervalo_tiempo = 1800 # media hora
wn.options.time.duration = duracion
wn.options.time.hydraulic_timestep = intervalo_tiempo
wn.options.time.report_timestep = intervalo_tiempo #cada media hora registra resultados
wn.options.hydraulic.required_pressure = 15 # Revisar las unidades de la presion
wn.options.hydraulic.minimum_pressure = 0

# Representamos la RDA como un grafo simple no dirigido para calcular sus
# metricas de resilencia topografica
G = wn.get_graph() # directed multigraph
uG = G.to_undirected() # undirected multigraph
sG = nx.Graph(uG) # undirected simple graph

#############################################################################
# Definimos la probabilidad de fuga de una tuberia basado en el grado de sus 
# nodos incidentes, la suma de las probabilidades de las tuberias debe ser 1

# Calculamos el grado para cada nodo
node_degree = G.degree()
# itera entre todos los nodos de la red y les asignamos a cada uno como un atrbuto
# su grado
for node_name, node in wn.nodes():
    node.grado = node_degree[node_name]

# Le asignamos a cada tuberia el valor del grado
for pipe_name, pipe in wn.pipes(): # iteramos en la tuberia
    start_node = wn.get_node(pipe.start_node)   # obtenemos el nodo inicial
    end_node = wn.get_node(pipe.end_node)       # obtenemos el nodo final 
    # el grado de la tuberia sera la suma de los grados de sus nodos entre 2
    pipe.grado = (start_node.grado + end_node.grado) / 2 

# asignamos probabilidad de fallo a cada tubería
# obtenemos una lista con los grado de cada tuberia
tuberia_grados = wn.query_link_attribute('grado',link_type=wntr.network.Pipe)
# a cada elemento de la lista de grados lo divide entre la suma de grados
# asi obtiene una lista de probabilidades de fallo
failure_probability = tuberia_grados/tuberia_grados.sum()
##############################################################################

# guarda una copia del modelo de red en f
f=open('wn.pickle','wb')
pickle.dump(wn,f)
f.close()

# Ejecuta el exprimento el numero de veces indicado en num_experimentos
num_experimentos = 2
results = {} # almacena los resultados de cada experimento
np.random.seed(67823) # Hace que en cada exprimento se elija una tubería diferente

# ejecuta los experimentos
for i in range(num_experimentos):

    # realiza la simulacion hidraulica
    wn.options.hydraulic.demand_model = 'PDD' # establece el modelo de demanda
    sim = wntr.sim.WNTRSimulator(wn)

    # almacena resultados de la simulacion
    results[i] = sim.run_sim()
    
    # Usa una copia del modelo de la red
    f=open('wn.pickle','rb')
    wn = pickle.load(f)
    f.close()

# Grafica los resultados: 1) disponibilidad de servicio de agua en cada nodo y
# nivel de agua en cada tanque
for i in results.keys():
    
    # calcula la demanda esperada en cada nodo (varia en el tiempo)
    expected_demand = wntr.metrics.expected_demand(wn)
    # calcula la demanda real en cada nodo (varia en el tiempo)
    demand = results[i].node['demand'].loc[:,wn.junction_name_list]
    # a partir de la demanda esperada y la demanda real (demanda real / demanda esperada)
    # calcula la disponibilidad del servicio de agua (wsa)
    wsa_nt = wntr.metrics.water_service_availability(expected_demand, demand)
    
    # Promedio de la disponibilidad de servicio de agua en todos los nodos
    wsa_t = wntr.metrics.water_service_availability(expected_demand.sum(axis=1), 
                                                  demand.sum(axis=1))
                               
    # Obtiene el nivel de agua en cada tanque
    tank_level = results[i].node['pressure'].loc[:,wn.tank_name_list]
    
    
    # Plot results
    plt.figure()
    
    plt.subplot(2,1,1)
    wsa_nt.index = wsa_nt.index / 3600 #convierte el tiempo a horas
    wsa_nt.plot(ax=plt.gca(), legend=False)
    wsa_t.index = wsa_t.index / 3600 #convierte el tiempo a horas
    wsa_t.plot(ax=plt.gca(), label='Promedio', color='k', linewidth=3.0, legend=True)
    plt.ylim( (-0.05, 1.05) )
    plt.ylabel('Disponibilidad de servicio')
    
    plt.subplot(2,1,2)
    tank_level.index = tank_level.index / 3600 #convierte el tiempo a horas
    tank_level.plot(ax=plt.gca())
    plt.ylim(ymin=0, ymax=12)
    plt.legend()
    plt.ylabel('Nivel del tanque (m)')
    plt.xlabel('Tiempo (hrs.)')