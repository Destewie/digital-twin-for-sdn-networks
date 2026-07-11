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
On one terminal:  
```vagrant up --provider=libvirt```   
On every terminal:  
```vagrant ssh```    

### Start a ryu controller  
On one terminal:  
```ryu-manager --verbose --observe-links ryu.app.rest_topology ryu.app.ofctl_rest ryu.app.simple_switch_13```  

### Start the mininet simulation
On another terminal:  
```sudo mn --topo linear,2 --mac --switch ovsk --controller remote```  

*Alternative topologies:*   
```sudo mn --topo single,2 --mac --switch ovsk --controller remote```  
```sudo mn --topo tree,depth=2,fanout=2 --mac --switch ovsk --controller remote```

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

### Useful mininet side-notes
- Launching ```py net.start()``` in mininet at runtime breaks some network configuations; expecially in switches and hosts that you created at runtime
- Remember to ```sudo mn -c``` every time that you exit from a mininet simulation

# How to interact with the digital twin
It is possible to use a handy CLI!  
Just type ```help``` or ```?``` to see the available commands.  
If you want to know more about a specific command, you can do ```help \<command\>```.  

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


# Known bugs
- Imagine the linear,2 topology. If I spawn a new node h3 and I attach it both to s1 and s2, when I delete the switch s1, the network configuration of h3 disappears, it is not configurable anymore and it also loses connectivity with the s2 (even if it should have been attached to it)

---

# Demos
*Before lounching these demos, ensure you successfully started the ryu controller, the mininet simulation and the digital twin*
*When nothing else is specified, execute these commands on the terminal dedicated to mininet.*  
*"(dt)" is used to indicate commands to lounch on the digital twin cli*

### Dynamic network modificatioon
```sudo mn --topo single,3 --mac --switch ovsk --controller remote```   
- Add a host  
```py net.addHost('h3')```  
```py net.addLink(h3, s1)```  
```py h3.setIP('10.0.0.3/8')```  
```py h3.setMAC('00:00:00:00:00:03')```  
```py s1.attach('s1-eth3')```    

- Add a switch and another host  
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

- To test if everything is mirrored on the digital twin:  
```(dt) summary```  
```(dt) hosts```  
```(dt) switches```  
```(dt) links```  

### Link failure detection
```sudo mn --topo single,3 --mac --switch ovsk --controller remote```   
- Toggle the state of a link  
```link h2 s1 down```  
```link h2 s1 up```  

### Host with 2 links & one of them fails 
```sudo mn --topo linear,3 --mac --switch ovsk --controller remote```   
- Attach an existing host to another switch and then destroy the link with the first switch and see that everythin still works
```py net.addLink(h1, s2)```  
```py h1.setIP('10.0.0.100/8', intf='h1-eth1')```   
```py h1.setMAC('00:00:00:00:00:10', intf='h1-eth1')```  
```py s2.attach('s2-eth4')```  
```link s1 h1 down```  
*Now is normal for pingall not to work! Because the 'h1' hostname is associated with the eth0 interface*  
- To test in mininet:  
```h2 ping 10.0.0.100```  
```h3 ping 10.0.0.100```  
- To test if everything is mirrored on the digital twin:  
```(dt) summary```  
```(dt) hosts```  

### Remove a switch
```sudo mn --topo linear,3 --mac --switch ovsk --controller remote```   
- Delete a switch  
```py net.delSwitch(s1)```
- To test if everything is mirrored on the digital twin:  
```(dt) links```  
```(dt) summary```  
```(dt) hosts```  

### What-if demo
```sudo mn --topo tree,depth=2,fanout=2 --mac --switch ovsk --controller remote```  
```h1 ping h4 -c 1000 &```  
- On the digital twin CLI:
```(dt) flows 0000000000000001```    
```(dt) whatif 0000000000000001 {"in_port":1} ["DROP"] 10```
