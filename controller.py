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

from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.tcp import tcp
from pox.lib.revent import *
from pox.lib.util import dpid_to_str
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.recoco import Timer

import time

log = core.getLogger()

FLOW_TIMEOUT = 30
DEBUG = False

ICMP_PROTOCOL = 1
TCP_PROTOCOL  = 6


# rules = [['10.0.0.1','10.0.0.2']]


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
        # load firewall policy
        self.lan = list()
        # lan to policy
        self.policys = list()
        self.premium = list()
        self._load_fw_policy('pox/mvn/policy.in')
        # core.listen_to_dependencies(self)
    
    def ip2mac(self, ip):
        return dpid_to_mac(int(ip.split('.')[-1]))

    def _load_fw_policy(self, policy_file):
        f = open(policy_file)
        config = f.readline().strip().split(' ')
        N, M = int(config[0]), int(config[1])
        lans = [int(i) for i in f.readline().strip().split(' ')]
        
        if N is len(lans): 
            log.info("valid input policy")
        for i in range(len(lans)):
            t_lan = list()
            for j in range(lans[i]):
                t_lan.append(f.readline().strip())
            self.lan.append(t_lan)
        for i in range(len(self.lan)):
            for j in range(i+1,len(self.lan)):
                for l1 in self.lan[i]:
                    for l2 in self.lan[j]:
                        self.policys.append([l1, l2])
        for i in range(M):
            self.premium.append(IPAddr(f.readline().strip()))
        # for k,v in self.lan.iteritems():
        #     log.info("%s -> %s",k,v)
        if DEBUG:
            log.info("policys: %s", self.policys)
            log.info("premium: %s", self.premium)
        
    # You can write other functions as you need.
    def _handle_expiration (self):
        for k,v in self.flow_table.iteritems():
            dpid = k
            remove_list = list()
            for mac, entry in v.iteritems():
                expires_time = entry.timeout
                if entry.is_expired():
                    if DEBUG:
                        log.info("%s's flow entry %s expired" % (dpid, mac))
                    remove_list.append(mac)
            if len(remove_list) > 0:
                if DEBUG:
                    log.info("%s's flow table before" % dpid)
                    for entry in self.flow_table[dpid].itervalues():
                        log.info(entry)
                for mac in remove_list:
                    del self.flow_table[dpid][mac]
                if DEBUG:
                    log.info("%s's flow table after" % dpid)
                    for entry in self.flow_table[dpid].itervalues():
                        log.info(entry)
        
    def _handle_PacketIn (self, event):

        dpid = event.connection.dpid
        inport = event.port
        packet = event.parsed
        p = packet.next

        if not packet.parsed:
            log.warning("%i %i ignoring unparsed packet", dpid, inport)
            return

        # install entries to the route table
        def install_enqueue(event, packet, outport, q_id):
            pass

        # Check the packet and decide how to route the packet
        def forward(outport, message = None, is_premium=False):
            message.data = event.ofp
            if is_premium:
                message.actions.append(of.ofp_action_enqueue(port = outport, queue_id=1))
            else:
                message.actions.append(of.ofp_action_output(port = outport))
            event.connection.send(msg)

        # When it knows nothing about the destination, flood but don't install the rule
        def flood (message = None, is_premium=False):
            message.data = event.ofp
            if is_premium:
                message.actions.append(of.ofp_action_enqueue(port = of.OFPP_FLOOD, queue_id=1))
            else:
                message.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
            # TODO: use OFPP_ALL and checksum to avoid 
            event.connection.send(msg)

        msg = of.ofp_packet_out()
        is_premium = False
        if isinstance(p, ipv4):
            if DEBUG:
                log.info("%s->%s, %s",p.srcip,p.dstip,p.protocol)
                log.info("%s->%s",packet.src,packet.dst)
            is_premium = p.srcip in self.premium or p.dstip in self.premium
        is_premium = False

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
            forward(outport, msg, is_premium)
        else:
            flood(msg, is_premium)

    def _handle_ConnectionUp(self, event):
        dpid = dpid_to_str(event.dpid)
        log.debug("Switch %s has come up.", dpid)
        
        # Send the firewall policies to the switch
        def sendFirewallPolicy(connection, policy):
            block = of.ofp_match()
            block.dl_src = EthAddr(self.ip2mac(policy[0]))
            block.dl_dst = EthAddr(self.ip2mac(policy[1]))
            block.dl_type = 0x0800 # IP
            block.nw_proto = TCP_PROTOCOL
            # block.tp_src = 4001 # block packet from 4001 port
            flow_mod = of.ofp_flow_mod()
            flow_mod.match = block
            connection.send(flow_mod)
        for p in self.policys:
            sendFirewallPolicy(event.connection, p)

def launch():
    # Run discovery and spanning tree modules
    pox.openflow.discovery.launch()
    pox.openflow.spanning_tree.launch()

    # Starting the controller module
    core.registerNew(Controller)
