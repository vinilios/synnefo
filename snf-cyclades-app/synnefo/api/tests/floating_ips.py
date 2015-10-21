# Copyright (C) 2010-2015 GRNET S.A. and individual contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.utils import simplejson as json
from snf_django.utils.testing import BaseAPITest, mocked_quotaholder
from synnefo.db.models import IPAddress, Network, Subnet, IPPoolTable
from synnefo.db import models_factory as mf

from mock import patch, Mock

from synnefo.cyclades_settings import cyclades_services
from synnefo.lib.services import get_service_path
from synnefo.lib import join_urls


network_path = get_service_path(cyclades_services, "network", version="v2.0")
URL = join_urls(network_path, "floatingips")
NETWORKS_URL = join_urls(network_path, "networks")
SERVERS_URL = join_urls(network_path, "servers")


floating_ips = IPAddress.objects.filter(floating_ip=True)


class FloatingIPAPITest(BaseAPITest):
    def setUp(self):
        self.pool = mf.NetworkWithSubnetFactory(floating_ip_pool=True,
                                                public=True,
                                                subnet__cidr="192.168.2.0/24",
                                                subnet__gateway="192.168.2.1")

    def test_no_floating_ip(self):
        response = self.get(URL)
        self.assertSuccess(response)
        self.assertEqual(json.loads(response.content)["floatingips"], [])

    def test_list_ips(self):
        ip = mf.IPv4AddressFactory(userid="user1", project="user1",
                                   floating_ip=True)
        with mocked_quotaholder():
            response = self.get(URL, "user1")
        self.assertSuccess(response)
        api_ip = json.loads(response.content)["floatingips"][0]
        self.assertEqual(api_ip,
                         {"instance_id": str(ip.nic.machine_id),
                          "floating_ip_address": ip.address,
                          "fixed_ip_address": None,
                          "id": str(ip.id),
                          "port_id": str(ip.nic.id),
                          "deleted": False,
                          "user_id": "user1",
                          "tenant_id": "user1",
                          "shared_to_project": False,
                          "floating_network_id": str(ip.network_id)})

    def test_get_ip(self):
        ip = mf.IPv4AddressFactory(userid="user1", project="user1",
                                   floating_ip=True)
        with mocked_quotaholder():
            response = self.get(URL + "/%s" % ip.id, "user1")
        self.assertSuccess(response)
        api_ip = json.loads(response.content)["floatingip"]
        self.assertEqual(api_ip,
                         {"instance_id": str(ip.nic.machine_id),
                          "floating_ip_address": ip.address,
                          "fixed_ip_address": None,
                          "id": str(ip.id),
                          "port_id": str(ip.nic.id),
                          "deleted": False,
                          "user_id": "user1",
                          "tenant_id": "user1",
                          "shared_to_project": False,
                          "floating_network_id": str(ip.network_id)})

    def test_wrong_user(self):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True)
        response = self.delete(URL + "/%s" % ip.id, "user2")
        self.assertItemNotFound(response)

    def test_deleted_ip(self):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True,
                                   deleted=True)
        response = self.delete(URL + "/%s" % ip.id, "user1")
        self.assertItemNotFound(response)

    def test_reserve(self):
        request = {"floatingip": {
            "floating_network_id": self.pool.id}
            }
        with mocked_quotaholder():
            response = self.post(URL, "test_user", json.dumps(request), "json")
        self.assertSuccess(response)
        api_ip = json.loads(response.content, encoding="utf-8")["floatingip"]
        ip = floating_ips.get()
        self.assertEqual(ip.address, "192.168.2.2")
        self.assertEqual(ip.nic, None)
        self.assertEqual(ip.network, self.pool)
        self.assertEqual(api_ip,
                         {"instance_id": None,
                          "floating_ip_address": "192.168.2.2",
                          "fixed_ip_address": None,
                          "id": str(ip.id),
                          "port_id": None,
                          "deleted": False,
                          "user_id": "test_user",
                          "tenant_id": "test_user",
                          "shared_to_project": False,
                          "floating_network_id": str(self.pool.id)})

    def test_reserve_empty_body(self):
        """Test reserve FIP without specifying network."""
        request = {"floatingip": {}}
        # delete all pools..
        IPPoolTable.objects.all().delete()
        Subnet.objects.all().delete()
        Network.objects.all().delete()
        # CASE: no floating IP pool
        with mocked_quotaholder():
            response = self.post(URL, "test_user", json.dumps(request), "json")
        self.assertConflict(response)
        # CASE: Full floating IP pool
        mf.NetworkWithSubnetFactory(floating_ip_pool=True, public=True,
                                    subnet__pool__size=0)
        with mocked_quotaholder():
            response = self.post(URL, "test_user", json.dumps(request), "json")
        self.assertConflict(response)
        # CASE: Available floating IP pool
        p1 = mf.NetworkWithSubnetFactory(floating_ip_pool=True, public=True,
                                         subnet__cidr="192.168.2.0/30",
                                         subnet__pool__size=1)
        with mocked_quotaholder():
            response = self.post(URL, "test_user", json.dumps(request), "json")
        self.assertSuccess(response)
        floating_ip = json.loads(response.content)["floatingip"]
        db_fip = IPAddress.objects.get(id=floating_ip["id"])
        self.assertEqual(db_fip.address, floating_ip["floating_ip_address"])
        self.assertTrue(db_fip.floating_ip)
        # Test that address is reserved
        ip_pool = p1.get_ip_pools()[0]
        self.assertFalse(ip_pool.is_available(db_fip.address))

    def test_reserve_no_pool(self):
        # Network is not a floating IP pool
        pool2 = mf.NetworkWithSubnetFactory(floating_ip_pool=False,
                                            public=True,
                                            subnet__cidr="192.168.2.0/24",
                                            subnet__gateway="192.168.2.1")
        request = {"floatingip": {
            'floating_network_id': pool2.id}
            }
        response = self.post(URL, "test_user", json.dumps(request), "json")
        self.assertConflict(response)

        # Full network
        net = mf.NetworkWithSubnetFactory(floating_ip_pool=True,
                                          public=True,
                                          subnet__cidr="192.168.2.0/31",
                                          subnet__gateway="192.168.2.1",
                                          subnet__pool__size=0)
        request = {"floatingip": {
            'floating_network_id': net.id}
            }
        response = self.post(URL, "test_user", json.dumps(request), "json")
        self.assertConflict(response)

    def test_reserve_with_address(self):
        request = {"floatingip": {
            "floating_network_id": self.pool.id,
            "floating_ip_address": "192.168.2.10"}
            }
        with mocked_quotaholder():
            response = self.post(URL, "test_user", json.dumps(request), "json")
        self.assertSuccess(response)
        ip = floating_ips.get()
        self.assertEqual(json.loads(response.content)["floatingip"],
                         {"instance_id": None,
                          "floating_ip_address": "192.168.2.10",
                          "fixed_ip_address": None,
                          "id": str(ip.id),
                          "port_id": None,
                          "deleted": False,
                          "user_id": "test_user",
                          "tenant_id": "test_user",
                          "shared_to_project": False,
                          "floating_network_id": str(self.pool.id)})

        # Already reserved
        with mocked_quotaholder():
            response = self.post(URL, "test_user", json.dumps(request), "json")
        self.assertFault(response, 409, "conflict")

        # Used by instance
        self.pool.reserve_address("192.168.2.20")
        request = {"floatingip": {
            "floating_network_id": self.pool.id,
            "floating_ip_address": "192.168.2.20"}
            }
        with mocked_quotaholder():
            response = self.post(URL, "test_user", json.dumps(request), "json")
        self.assertFault(response, 409, "conflict")

        # Address out of pool
        request = {"floatingip": {
            "floating_network_id": self.pool.id,
            "floating_ip_address": "192.168.3.5"}
            }
        with mocked_quotaholder():
            response = self.post(URL, "test_user", json.dumps(request), "json")
        self.assertBadRequest(response)

    '''
    @patch("synnefo.db.models.get_rapi_client")
    def test_reserve_and_connect(self, mrapi):
        vm = mf.VirtualMachineFactory(userid="test_user")
        request = {"floatingip": {
            "floating_network_id": self.pool.id,
            "floating_ip_address": "192.168.2.12",
            "device_id": vm.id}
            }
        response = self.post(URL, "test_user", json.dumps(request), "json")
        ip = floating_ips.get()
        api_ip = json.loads(response.content, "utf-8")["floatingip"]
        self.assertEqual(api_ip,
                         {"instance_id": str(vm.id),
                          "floating_ip_address": "192.168.2.12",
                          "fixed_ip_address": None,
                          "id": str(ip.id),
                          "port_id": str(vm.nics.all()[0].id),
                          "floating_network_id": str(self.pool.id)})

    @patch("synnefo.db.models.get_rapi_client")
    def test_update_attach(self, mrapi):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True, nic=None)
        vm = mf.VirtualMachineFactory(userid="user1")
        request = {"floatingip": {
            "device_id": vm.id}
            }
        with mocked_quotaholder():
            response = self.put(URL + "/%s" % ip.id, "user1",
                                json.dumps(request), "json")
        self.assertEqual(response.status_code, 202)

    def test_update_attach_conflict(self):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True)
        vm = mf.VirtualMachineFactory(userid="user1")
        request = {"floatingip": {
            "device_id": vm.id}
            }
        with mocked_quotaholder():
            response = self.put(URL + "/%s" % ip.id, "user1",
                                json.dumps(request), "json")
        self.assertEqual(response.status_code, 409)

    @patch("synnefo.db.models.get_rapi_client")
    def test_update_dettach(self, mrapi):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True)
        request = {"floatingip": {
            "device_id": None}
            }
        mrapi().ModifyInstance.return_value = 42
        with mocked_quotaholder():
            response = self.put(URL + "/%s" % ip.id, "user1",
                                json.dumps(request), "json")
        self.assertEqual(response.status_code, 202)

    def test_update_dettach_unassociated(self):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True, nic=None)
        request = {"floatingip": {}}
        with mocked_quotaholder():
            response = self.put(URL + "/%s" % ip.id, "user1",
                                json.dumps(request), "json")
        self.assertEqual(response.status_code, 400)

    def test_release_in_use(self):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True)
        vm = mf.VirtualMachineFactory(userid="user1")
        request = {"floatingip": {
            "device_id": vm.id}
            }
        with mocked_quotaholder():
            response = self.put(URL + "/%s" % ip.id, "user1",
                                json.dumps(request), "json")
        self.assertEqual(response.status_code, 409)

    @patch("synnefo.db.models.get_rapi_client")
    def test_update_dettach(self, mrapi):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True)
        request = {"floatingip": {
            "device_id": None}
            }
        mrapi().ModifyInstance.return_value = 42
        with mocked_quotaholder():
            response = self.put(URL + "/%s" % ip.id, "user1",
                                json.dumps(request), "json")
        self.assertEqual(response.status_code, 202)

    def test_update_dettach_unassociated(self):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True, nic=None)
        request = {"floatingip": {}}
        with mocked_quotaholder():
            response = self.put(URL + "/%s" % ip.id, "user1",
                                json.dumps(request), "json")
        self.assertEqual(response.status_code, 400)

    def test_release_in_use(self):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True)
        vm = ip.nic.machine
        with mocked_quotaholder():
            response = self.delete(URL + "/%s" % ip.id, ip.userid)
        self.assertFault(response, 409, "conflict")
    '''

    def test_update(self):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True, nic=None)
        with mocked_quotaholder():
            response = self.put(URL + "/%s" % ip.id, ip.userid)
        self.assertEqual(response.status_code, 501)

    def test_release(self):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True, nic=None)
        with mocked_quotaholder():
            response = self.delete(URL + "/%s" % ip.id, ip.userid)
        self.assertSuccess(response)
        ips_after = floating_ips.filter(id=ip.id)
        self.assertEqual(len(ips_after), 0)

    @patch("synnefo.logic.backend", Mock())
    def test_delete_network_with_floating_ips(self):
        ip = mf.IPv4AddressFactory(userid="user1", floating_ip=True,
                                   network=self.pool, nic=None)
        # Mark the network as non-pubic to not get 403
        network = ip.network
        network.public = False
        network.save()
        # Cannot remove network with floating IPs
        with mocked_quotaholder():
            response = self.delete(NETWORKS_URL + "/%s" % self.pool.id,
                                   self.pool.userid)
        self.assertConflict(response)
        # But we can with only deleted Floating Ips
        ip.deleted = True
        ip.save()
        with mocked_quotaholder():
            response = self.delete(NETWORKS_URL + "/%s" % self.pool.id,
                                   self.pool.userid)
        self.assertSuccess(response)

'''
POOLS_URL = join_urls(compute_path, "os-floating-ip-pools")


class FloatingIPPoolsAPITest(BaseAPITest):
    def test_no_pool(self):
        response = self.get(POOLS_URL)
        self.assertSuccess(response)
        self.assertEqual(json.loads(response.content)["floating_ip_pools"], [])

    def test_list_pools(self):
        net = mf.NetworkWithSubnetFactory(floating_ip_pool=True,
                                          public=True,
                                          subnet__cidr="192.168.2.0/30",
                                          subnet__gateway="192.168.2.1",
                                          subnet__pool__size=1,
                                          subnet__pool__offset=1)
        mf.NetworkWithSubnetFactory(public=True, deleted=True)
        mf.NetworkWithSubnetFactory(public=False, deleted=False)
        mf.NetworkWithSubnetFactory(public=True, floating_ip_pool=False)
        response = self.get(POOLS_URL)
        self.assertSuccess(response)
        self.assertEqual(json.loads(response.content)["floating_ip_pools"],
                         [{"name": str(net.id), "size": 1, "free": 1}])


class FloatingIPActionsTest(BaseAPITest):
    def setUp(self):
        self.vm = VirtualMachineFactory()
        self.vm.operstate = "ACTIVE"
        self.vm.save()

    def test_bad_request(self):
        url = SERVERS_URL + "/%s/action" % self.vm.id
        response = self.post(url, self.vm.userid, json.dumps({}), "json")
        self.assertBadRequest(response)
        response = self.post(url, self.vm.userid,
                             json.dumps({"addFloatingIp": {}}),
                             "json")
        self.assertBadRequest(response)

    @patch('synnefo.logic.rapi_pool.GanetiRapiClient')
    def test_add_floating_ip(self, mock):
        # Not exists
        url = SERVERS_URL + "/%s/action" % self.vm.id
        request = {"addFloatingIp": {"address": "10.0.0.1"}}
        response = self.post(url, self.vm.userid, json.dumps(request), "json")
        self.assertItemNotFound(response)
        # In use
        ip = mf.IPv4AddressFactory(floating_ip=True, userid=self.vm.userid)
        request = {"addFloatingIp": {"address": ip.address}}
        response = self.post(url, self.vm.userid, json.dumps(request), "json")
        self.assertConflict(response)
        # Success
        ip = mf.IPv4AddressFactory(floating_ip=True, nic=None,
                                   userid=self.vm.userid)
        request = {"addFloatingIp": {"address": ip.address}}
        mock().ModifyInstance.return_value = 1
        response = self.post(url, self.vm.userid, json.dumps(request), "json")
        self.assertEqual(response.status_code, 202)
        ip_after = floating_ips.get(id=ip.id)
        self.assertEqual(ip_after.nic.machine, self.vm)
        nic = self.vm.nics.get()
        nic.state = "ACTIVE"
        nic.save()
        response = self.get(SERVERS_URL + "/%s" % self.vm.id,
                            self.vm.userid)
        self.assertSuccess(response)
        nic = json.loads(response.content)["server"]["attachments"][0]
        self.assertEqual(nic["OS-EXT-IPS:type"], "floating")

    @patch('synnefo.logic.rapi_pool.GanetiRapiClient')
    def test_remove_floating_ip(self, mock):
        # Not exists
        url = SERVERS_URL + "/%s/action" % self.vm.id
        request = {"removeFloatingIp": {"address": "10.0.0.1"}}
        response = self.post(url, self.vm.userid, json.dumps(request), "json")
        self.assertBadRequest(response)
        # Not In Use
        ip = mf.IPv4AddressFactory(floating_ip=True, nic=None,
                                   userid=self.vm.userid)
        request = {"removeFloatingIp": {"address": ip.address}}
        response = self.post(url, self.vm.userid, json.dumps(request), "json")
        self.assertBadRequest(response)
        # Success
        ip = mf.IPv4AddressFactory(floating_ip=True,
                                   userid=self.vm.userid, nic__machine=self.vm)
        request = {"removeFloatingIp": {"address": ip.address}}
        mock().ModifyInstance.return_value = 2
        response = self.post(url, self.vm.userid, json.dumps(request), "json")
        self.assertEqual(response.status_code, 202)
        # Yet used. Wait for the callbacks
        ip_after = floating_ips.get(id=ip.id)
        self.assertEqual(ip_after.nic.machine, self.vm)
'''
