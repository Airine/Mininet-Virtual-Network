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
import pox.lib.packet as pkt

from pox.lib.revent import *
from pox.lib.util import dpid_to_str
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.recoco import Timer

import time

log = core.getLogger()

FLOW_TIMEOUT = 30
DEBUG = True

rules = [['00:00:00:00:00:01','00:00:00:00:00:02'],['00:00:00:00:00:02', '00:00:00:00:00:04'],['00:00:00:00:00:07','00:00:00:00:00:02']]


def dpid_to_mac (dpid):
  return EthAddr("%012x" % (dpid & 0xffFFffFFffFF))

class Entry(object):
    """
    Not strictly an entry in flow table.
    """
    def __init__(self, port, mac):
        self.timeout = time.time() + FLOW_TIMEOUT
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
    
    def is_expired(self):
        return time.time() > self.timeout;

class Controller(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)

        # dpid -> {mac->entry}
        self.flow_table = dict()
        # handles entry expiring
        self._expire_timer = Timer(5, self._handle_expiration, recurring=True)
        # core.listen_to_dependencies(self)
        
    # You can write other functions as you need.

    def _handle_expiration (self):
        for k,v in self.flow_table.iteritems():
            dpid = k
            remove_list = list()
            for mac, entry in v.iteritems():
                expires_time = entry.timeout
                if entry.is_expired():
                    log.info("%s's flow entry %s expired" % (dpid, mac))
                    remove_list.append(mac)
            if len(remove_list) > 0:
                log.info("%s's flow table before" % dpid)
                for entry in self.flow_table[dpid].itervalues():
                    log.info(entry)
                for mac in remove_list:
                    del self.flow_table[dpid][mac]
                log.info("%s's flow table after" % dpid)
                for entry in self.flow_table[dpid].itervalues():
                    log.info(entry)
        
    def _handle_PacketIn (self, event):

        dpid = event.connection.dpid
        inport = event.port
        packet = event.parsed

        p = packet.next
        if isinstance(p, ipv4) and DEBUG:
            log.info("%s->%s, %s",p.srcip,p.dstip,p.protocol)

        if not packet.parsed:
            log.warning("%i %i ignoring unparsed packet", dpid, inport)
            return
        
        # ip = packet.find('ipv4')
        # if ip is not None:
        #     log.info("srcip: %s" % ip)
        # tcp = packet.find("tcp")
        # if tcp is not None:
        #     log.info("TCP pkt!")
        # if packet.type == pkt.IP_TYPE:
        #     ip_pkt = packet.payload
        #     log.info("This is a IP packet.")
        #     if ip_pkt.protocol == pkt.TCP_PROTOCOL:
        #         log.info("This is a TCP packet.")

        # install entries to the route table
        def install_enqueue(event, packet, outport, q_id):
            pass

        # Check the packet and decide how to route the packet
        def forward(outport, message = None):
            message.data = event.ofp
            message.actions.append(of.ofp_action_output(port = outport))
            event.connection.send(msg)

        # When it knows nothing about the destination, flood but don't install the rule
        def flood (message = None):
            message.data = event.ofp
            message.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
            # TODO: use OFPP_ALL and checksum to avoid 
            event.connection.send(msg)

        msg = of.ofp_packet_out()

        # update flow_table
        if dpid not in self.flow_table:
            if DEBUG:
                log.info("building flow table for switch %s", dpid)
            self.flow_table[dpid] = dict()
        
        if packet.src not in self.flow_table[dpid]:
            t_entry = Entry(inport, packet.src)
            self.flow_table[dpid][packet.src] = t_entry
            if DEBUG:
                log.info("adding entry %s in %s's flow table" % (t_entry, dpid))    
        
        if packet.dst in self.flow_table[dpid]:
            outport = self.flow_table[dpid][packet.dst].port
            forward(outport, msg)
        else:
            flood(msg)

    def _handle_ConnectionUp(self, event):
        dpid = dpid_to_str(event.dpid)
        log.debug("Switch %s has come up.", dpid)
        
        # Send the firewall policies to the switch
        def sendFirewallPolicy(connection, policy):

            pass
        
        for rule in rules:
            block = of.ofp_match()
            block.dl_src = EthAddr(rule[0])
            block.dl_dst = EthAddr(rule[1])
            flow_mod = of.ofp_flow_mod()
            flow_mod.match = block
            event.connection.send(flow_mod)
        # for i in [FIREWALL POLICIES]:
        #     sendFirewallPolicy(event.connection, i)
            

def launch():
    # Run discovery and spanning tree modules
    pox.openflow.discovery.launch()
    pox.openflow.spanning_tree.launch()

    # Starting the controller module
    core.registerNew(Controller)
