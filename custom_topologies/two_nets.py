from mininet.topo import Topo

class TwoNetsTopo(Topo):
    def build(self):
        # Switch for Network 1
        s1 = self.addSwitch('s1')
        # Switch for Network 2
        s2 = self.addSwitch('s2')

        # Hosts on Network 1 (subnet 10.0.1.0/24)
        h1 = self.addHost('h1', ip='10.0.1.1/24')
        h2 = self.addHost('h2', ip='10.0.1.2/24')
        self.addLink(h1, s1)
        self.addLink(h2, s1)

        # Hosts on Network 2 (subnet 10.0.2.0/24)
        h3 = self.addHost('h3', ip='10.0.2.1/24')
        h4 = self.addHost('h4', ip='10.0.2.2/24')
        self.addLink(h3, s2)
        self.addLink(h4, s2)

topos = { 'twonets': (lambda: TwoNetsTopo()) }
