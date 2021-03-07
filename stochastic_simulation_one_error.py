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

# Le asignamos a cada tuberia el valor del grado
for pipe_name, pipe in wn.pipes(): # iteramos en la tuberia
    pipe.grado = 1

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

    # Con base en la probabilidad de fuga selecciona la tuberia que tendra fuga
    pipes_to_fail = np.random.choice(failure_probability.index, num_fugas,
                                     replace=False,
                                     p=failure_probability.values)

    # Selecciona el tiempo en que comienza la fuga (entre 1 y 10 am)
    time_of_failure = np.round(np.random.uniform(1,10,1)[0], 2)

    # Selecciona la duracion de la fuga entre 12 y 24hrs
    duration_of_failure = np.round(np.random.uniform(12,24,1)[0], 2)
    
    # Agrega las fugas al modelo
    for pipe_to_fail in pipes_to_fail:
        pipe = wn.get_link(pipe_to_fail)
        # el diamtero de la fuga es una tercera parte del diametro de la tuberia
        leak_diameter = pipe.diameter*0.3
        # calcula el area de la fuga
        leak_area=3.14159*(leak_diameter/2)**2
        #agrega la fuga en el tiempo y con la duracion estimada
        wn = wntr.morph.split_pipe(wn, pipe_to_fail, pipe_to_fail + '_B', pipe_to_fail+'leak_node')
        leak_node = wn.get_node(pipe_to_fail+'leak_node')
        leak_node.add_leak(wn, area=leak_area,
                          start_time=time_of_failure*3600,
                          end_time=(time_of_failure + duration_of_failure)*3600)

    # realiza la simulacion hidraulica
    wn.options.hydraulic.demand_model = 'PDD' # establece el modelo de demanda
    sim = wntr.sim.WNTRSimulator(wn)
    print('Tuberia con fuga : ' + str(pipes_to_fail) + ', La fuga comenzo a las: ' + \
                str(time_of_failure) + ', y termino: ' + \
                str(time_of_failure+duration_of_failure))
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