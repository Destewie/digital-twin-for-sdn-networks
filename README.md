# **Softwarized and virtualized mobile networks project** 
*@UniTrento*  
Professor: Fabrizio Granelli

## Project requirements:
**GOAL**: To buid a script that allows to generate the Digital Twin of an SDN network
- Exploit RYU Northbound RestAPI to retrieve the topology- and traffic-related information
- The procedure should be completely automated
- Runtime, changes to the Physical Twin are reproduced automatically to the Digital Twin

---

## How to start everything
### Open terminals
Open at least 3 of them:
- one for mininet
- one for the ryu controller
- one for the digital twin script

### Spin up and connect to the vms
On every terminal:  
```vagrant up --provider=libvirt```  
```vagrant ssh```    

### Start a ryu controller  
On one terminal:  
```ryu-manager --verbose --observe-links ryu.app.rest_topology ryu.app.ofctl_rest ryu.app.simple_switch_13```  

### Start the mininet simulation
On another terminal:  
```sudo mn --topo single,2 --mac --switch ovsk --controller remote```  

*Alternative topology:*   
```sudo mn --topo linear,2 --mac --switch ovsk --controller remote```  


### Finally start the digital twin script
On the last terminal:  

1. Clone this repository inside the comnetsemu VM:  
```git clone https://github.com/Destewie/digital-twin-for-sdn-networks.git```

2. Install python dependencies inside the comnetsemu VM:  
```pip install networkx requests```

3. Start the digital twin:  
```cd digital-twin-for-sdn-networks```  
```python3 main.py --interval 2```  

---

## How to modify the mininet network through its CLI
### Disable/enable a link
On the mininet CLI  
```link h2 s1 down```  
```pingall```  
```link h2 s1 up```  


### Add a host
*Note that if you don't add this host, port names will change if you try to add another switch in the following set of commands*  
```py net.addHost('h3')```  
```py net.addLink(h3, s1)```  
```py h3.setIP('10.0.0.3/8')```  
```py h3.setMAC('00:00:00:00:00:03')```  
```py s1.attach('s1-eth3')```  
  
### Add a switch and a host
```py net.addSwitch('s2')```  
```py net.addLink(s1, s2)```
```py net.addHost('h4')```  
```py net.addLink(h4, s2)```
```py h4.setIP('10.0.0.4/8')```  
```py h4.setMAC('00:00:00:00:00:04')```  
```py s1.attach('s1-eth4')```  
```py s2.attach('s2-eth1')```  
```py s2.attach('s2-eth2')```  
```py s2.start([net.controllers[0]])```

  
### Remove a switch
```py net.delSwitch(s1)```  

### Useful side-notes
- Launching ```py net.start()``` in mininet at runtime breaks some network configuations; expecially in switches and hosts that you created at runtime
- Remember to ```sudo mn -c``` every time that you exit from a mininet simulation

# How to interact with the digital twin
It is possible to use a handy CLI!  
Just type 'help' or '?' to see the available commands.  
If you want to know more about a specific command, you can do help <command>.  

Available digital twin CLI commands:
- help
- summary
- hosts
- switches
- links
- flows
- whatif 
- save
- quit

## Whatif command
Detects which flows will be affected by a potential new rule. \ 
Examples:
- ```whatif 0000000000000001 '{"in_port":1}' '["DROP"]' 10```
- ```whatif 0000000000000001 '{"dl_src":"00:00:00:00:00:01","dl_dst":"00:00:00:00:00:02"}' '["OUTPUT:3"]' 5```
- ```whatif 0000000000000001 '{"in_port":1,"dl_src":"00:00:00:00:00:01"}' '["OUTPUT:3"]' 10```
