'''
Please add your name: Tian Runxin
Please add your matric number: A0209160N
'''

import os
import sys
import atexit
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.topolib import TreeTopo
from mininet.link import Link, TCLink
from mininet.node import RemoteController

net = None

class MyTopo(Topo):
            
    def build(self, input_file='topology.in'):

        f = open(input_file)
        config = f.readline().strip().split(' ')
        lines = f.readlines()
        f.close()

        N, M, L = [int(i) for i in config]

        for n in range(N):
            self.addHost('h%d' % (n+1))
        for m in range(M):
            sconfig = {'dpid': "%016x" % (m+1)}
            self.addSwitch('s%d' % (m+1), **sconfig)

        for l in lines:
            d1, d2, bandwidth = l.strip().split(',')
            self.addLink(d1, d2)

def startNetwork():
    info('** Creating the tree network\n')
    # topo = TreeTopo(depth=2, fanout=2)

    topo = MyTopo()
    global net
    net = Mininet(topo=topo, link = Link,
                  controller=lambda name: RemoteController(name, ip='192.168.56.1'), #192.168.56.1
                  listenPort=6633, autoSetMacs=True)

    info('** Starting the network\n')
    net.start()

    # Create QoS Queues
    os.system('sudo ovs-vsctl -- set Port eth0 qos=@newqos \
               -- --id=@newqos create QoS type=linux-htb other-config:max-rate=10000000 queues=0=@q0,1=@q1 \
               -- --id=@q0 create queue other-config:max-rate=5000000 \
               -- --id=@q1 create queue other-config:min-rate=8000000 ')
            #    -- --id=@q2 create queue other-config:max-rate=5000000')

    info('** Running CLI\n')
    CLI(net)

def stopNetwork():
    if net is not None:
        net.stop()
        # Remove QoS and Queues
        os.system('sudo ovs-vsctl --all dcestroy Qos')
        os.system('sudo ovs-vsctl --all destroy Queue')


if __name__ == '__main__':
    # Force cleanup on exit by registering a cleanup function
    atexit.register(stopNetwork)

    # Tell mininet to print useful information
    setLogLevel('info')
    startNetwork()
