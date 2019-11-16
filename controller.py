'''
Please add your name: Tian Runxin
Please add your matric number: A0209160N
'''

import sys
import os
from sets import Set

from pox.core import core

import pox.openflow.libopenflow_01 as of
import pox.openflow.discovery
import pox.openflow.spanning_tree

from pox.lib.revent import *
from pox.lib.util import dpid_to_str
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.addresses import IPAddr, EthAddr

log = core.getLogger()

def dpid_to_mac (dpid):
  return EthAddr("%012x" % (dpid & 0xffFFffFFffFF))

class Entry(object):
    """
    Not strictly an entry in flow table.
    """
    def __init__(self, port, mac):
        # self.timeout = time.time() + FLOW_TIMEOUT
        self.port = port
        self.mac = mac

    def __eq__ (self, other):
        if type(other) == tuple:
            return (self.port,self.mac)==other
        else:
            return (self.port,self.mac)==(other.port,other.mac)
    def __ne__ (self, other):
        return not self.__eq__(other)
    
    def __str__ (self):
        return "%s\t %s" % (self.mac, self.port)

class Controller(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)

        # dpid -> {mac->entry}
        self.flow_table = dict()
        
    # You can write other functions as you need.
        
    def _handle_PacketIn (self, event):
        # install entries to the route table
        def install_enqueue(event, packet, outport, q_id):
            pass

        # Check the packet and decide how to route the packet
        def forward(outport, message = None):

            pass

        # When it knows nothing about the destination, flood but don't install the rule
        def flood (message = None):
            message.data = event.ofp
            message.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
            event.connection.send(msg)

        dpid = event.connection.dpid
        inport = event.port
        packet = event.parsed
        if not packet.parsed:
            log.warning("%i %i ignoring unparsed packet", dpid, inport)
            return

        # log.info('dpid\tinport\tpacket')        
        # log.info('%s\t\t%s\t%s\t' %(dpid,inport,packet))
        # log.info('src\tdst')
        # log.info('%s\t%s'%(packet.src, packet.dst))

        msg = of.ofp_packet_out()

        # update flow_table
        if dpid not in self.flow_table:
            log.info("building flow table for switch %s", dpid)
            self.flow_table[dpid] = dict()
        
        if packet.src not in self.flow_table[dpid]:
            t_entry = Entry(inport, packet.src)
            self.flow_table[dpid][packet.src] = t_entry
            log.info("adding entry %s in %s's flow table" % (t_entry, dpid))    
        
        if packet.dst in self.flow_table[dpid]:
            log.info("%s -> %s by flow table" % (dpid, packet.dst))
            outport = self.flow_table[dpid][packet.dst].port
            forward(outport, msg)
        else:
            flood(msg)

        # log.info("%s's flow table" % dpid)
        # for entry in self.flow_table[dpid].itervalues():
        #     log.info(entry)

    def _handle_ConnectionUp(self, event):
        dpid = dpid_to_str(event.dpid)
        log.debug("Switch %s has come up.", dpid)
        
        # Send the firewall policies to the switch
        def sendFirewallPolicy(connection, policy):
            pass

        # for i in [FIREWALL POLICIES]: I I /
        #     sendFirewallPolicy(event.connection, i)
            

def launch():
    # Run discovery and spanning tree modules
    pox.openflow.discovery.launch()
    pox.openflow.spanning_tree.launch()

    # Starting the controller module
    core.registerNew(Controller)
