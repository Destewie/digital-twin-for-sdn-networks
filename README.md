**Networking 2** *(a.k.a. Softwarized and virtualized mobile networks)* **project** (at UniTrento).  
Professor: Fabrizio Granelli.

## Project requirements:
- GOAL: To buid a script that allows to generate the Digital Twin of an SDN network
- Exploit RYU Northbound RestAPI to retrieve the topology- and traffic-related information
- The procedure should be completely automated
- Runtime, changes to the Physical Twin are reproduced automatically to the Digital Twin

---

## How to make the start everything
#### Open terminals
Open at least 3 of them:
- one for mininet
- one for the ryu controller
- one for the digital twin script

#### Spin up and connect to the vms
On every terminal:  
```vagrant up```  
```vagrant ssh```    

#### Start the mininet simulation
On one terminal:
```sudo mn --topo single,3 --mac --switch ovsk --controller remote```

#### Start a ryu controller  
On another terminal:
```ryu-manager --verbose ryu.app.rest_topology ryu.app.ofctl_rest ryu.app.simple_switch_13```

#### Finally start the digital twin script
On the last terminal:
```cd digital-twin-for-sdn-networks```
```python3 main.py --interval 2```

---

## How to modify the mininet network
On the mininet cli
- ```link h2 s1 down```
- ```pingall```
- ```link h2 s1 up```
