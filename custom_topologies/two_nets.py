from mininet.topo import Topo

class VLANTopo(Topo):
    def build(self):
        # Add a single switch
        s1 = self.addSwitch('s1')

        # Add hosts and assign them to different VLANs
        h1 = self.addHost('h1', ip='10.0.1.1/24')
        h2 = self.addHost('h2', ip='10.0.1.2/24')
        h3 = self.addHost('h3', ip='10.0.2.1/24')
        h4 = self.addHost('h4', ip='10.0.2.2/24')

        # Connect hosts to the switch with specific VLAN tags
        self.addLink(h1, s1, port1=1, port2=1)
        self.addLink(h2, s1, port1=1, port2=2)  # Same VLAN as h1
        self.addLink(h3, s1, port1=2, port2=3)  # Different VLAN
        self.addLink(h4, s1, port1=2, port2=4)  # Same VLAN as h3

topos = { 'vlan': (lambda: VLANTopo()) }
