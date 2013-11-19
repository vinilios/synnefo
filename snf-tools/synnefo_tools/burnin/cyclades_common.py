# Copyright 2013 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

"""
Utility functions for Cyclades Tests
Cyclades require a lot helper functions and `common'
had grown too much.

"""

import time
import socket
import random
import subprocess

from synnefo_tools.burnin.common import BurninTests


# Too many public methods. pylint: disable-msg=R0904
class CycladesTests(BurninTests):
    """Extends the BurninTests class for Cyclades"""
    def _try_until_timeout_expires(self, opmsg, check_fun):
        """Try to perform an action until timeout expires"""
        assert callable(check_fun), "Not a function"

        action_timeout = self.action_timeout
        action_warning = self.action_warning
        if action_warning > action_timeout:
            action_warning = action_timeout

        start_time = time.time()
        while (start_time + action_warning) > time.time():
            try:
                return check_fun()
            except Retry:
                time.sleep(self.query_interval)
        self.warning("Operation `%s' is taking too long", opmsg)
        while (start_time + action_timeout) > time.time():
            try:
                return check_fun()
            except Retry:
                time.sleep(self.query_interval)
        self.error("Operation `%s' timed out", opmsg)
        self.fail("time out")

    def _get_list_of_servers(self, detail=False):
        """Get (detailed) list of servers"""
        if detail:
            self.info("Getting detailed list of servers")
        else:
            self.info("Getting simple list of servers")
        return self.clients.cyclades.list_servers(detail=detail)

    def _get_server_details(self, server):
        """Get details for a server"""
        self.info("Getting details for server %s with id %s",
                  server['name'], server['id'])
        return self.clients.cyclades.get_server_details(server['id'])

    def _create_server(self, name, image, flavor):
        """Create a new server"""
        self.info("Creating a server with name %s", name)
        self.info("Using image %s with id %s", image['name'], image['id'])
        self.info("Using flavor %s with id %s", flavor['name'], flavor['id'])
        server = self.clients.cyclades.create_server(
            name, flavor['id'], image['id'])

        self.info("Server id: %s", server['id'])
        self.info("Server password: %s", server['adminPass'])

        self.assertEqual(server['name'], name)
        self.assertEqual(server['flavor']['id'], flavor['id'])
        self.assertEqual(server['image']['id'], image['id'])
        self.assertEqual(server['status'], "BUILD")

        return server

    def _get_connection_username(self, server):
        """Determine the username to use to connect to the server"""
        users = server['metadata'].get("users", None)
        ret_user = None
        if users is not None:
            user_list = users.split()
            if "root" in user_list:
                ret_user = "root"
            else:
                ret_user = random.choice(user_list)
        else:
            # Return the login name for connections based on the server OS
            self.info("Could not find `users' metadata in server. Let's guess")
            os_value = server['metadata'].get("os")
            if os_value in ("Ubuntu", "Kubuntu", "Fedora"):
                ret_user = "user"
            elif os_value in ("windows", "windows_alpha1"):
                ret_user = "Administrator"
            else:
                ret_user = "root"

        self.assertIsNotNone(ret_user)
        self.info("User's login name: %s", ret_user)
        return ret_user

    def _insist_on_server_transition(self, server, curr_status, new_status):
        """Insist on server transiting from curr_status to new_status"""
        def check_fun():
            """Check server status"""
            srv = self.clients.cyclades.get_server_details(server['id'])
            if srv['status'] == curr_status:
                raise Retry()
            elif srv['status'] == new_status:
                return
            else:
                msg = "Server %s went to unexpected status %s"
                self.error(msg, server['name'], srv['status'])
                self.fail(msg % (server['name'], srv['status']))
        opmsg = "Waiting for server %s to transit from %s to %s"
        self.info(opmsg, server['name'], curr_status, new_status)
        opmsg = opmsg % (server['name'], curr_status, new_status)
        self._try_until_timeout_expires(opmsg, check_fun)

    def _insist_on_tcp_connection(self, family, host, port):
        """Insist on tcp connection"""
        def check_fun():
            """Get a connected socket from the specified family to host:port"""
            sock = None
            for res in socket.getaddrinfo(host, port, family,
                                          socket.SOCK_STREAM, 0,
                                          socket.AI_PASSIVE):
                fam, socktype, proto, _, saddr = res
                try:
                    sock = socket.socket(fam, socktype, proto)
                except socket.error:
                    sock = None
                    continue
                try:
                    sock.connect(saddr)
                except socket.error:
                    sock.close()
                    sock = None
                    continue
            if sock is None:
                raise Retry
            return sock
        familystr = {socket.AF_INET: "IPv4", socket.AF_INET6: "IPv6",
                     socket.AF_UNSPEC: "Unspecified-IPv4/6"}
        opmsg = "Connecting over %s to %s:%s"
        self.info(opmsg, familystr.get(family, "Unknown"), host, port)
        opmsg = opmsg % (familystr.get(family, "Unknown"), host, port)
        return self._try_until_timeout_expires(opmsg, check_fun)

    def _get_ip(self, server, version):
        """Get the public IP of a server from the detailed server info"""
        assert version in (4, 6)

        nics = server['attachments']
        public_addrs = None
        for nic in nics:
            net_id = nic['network_id']
            if self.clients.cyclades.get_network_details(net_id)['public']:
                public_addrs = nic['ipv' + str(version)]

        self.assertIsNotNone(public_addrs)
        msg = "Servers %s public IPv%s is %s"
        self.info(msg, server['name'], version, public_addrs)
        return public_addrs

    def _insist_on_ping(self, ip_addr, version):
        """Test server responds to a single IPv4 of IPv6 ping"""
        def check_fun():
            """Ping to server"""
            assert version in (4, 6)
            cmd = ("ping%s -c 3 -w 20 %s" %
                   ("6" if version == 6 else "", ip_addr))
            ping = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            ping.communicate()
            ret = ping.wait()
            if ret != 0:
                raise Retry
        opmsg = "Sent IPv%s ping requests to %s"
        self.info(opmsg, version, ip_addr)
        opmsg = opmsg % (version, ip_addr)
        self._try_until_timeout_expires(opmsg, check_fun)


class Retry(Exception):
    """Retry the action

    This is used by _try_unit_timeout_expires method.

    """
