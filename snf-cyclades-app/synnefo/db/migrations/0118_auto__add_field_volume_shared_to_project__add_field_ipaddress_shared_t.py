# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Volume.shared_to_project'
        db.add_column('db_volume', 'shared_to_project',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'IPAddress.shared_to_project'
        db.add_column('db_ipaddress', 'shared_to_project',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'VirtualMachine.shared_to_project'
        db.add_column('db_virtualmachine', 'shared_to_project',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

        # Adding field 'Network.shared_to_project'
        db.add_column('db_network', 'shared_to_project',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Volume.shared_to_project'
        db.delete_column('db_volume', 'shared_to_project')

        # Deleting field 'IPAddress.shared_to_project'
        db.delete_column('db_ipaddress', 'shared_to_project')

        # Deleting field 'VirtualMachine.shared_to_project'
        db.delete_column('db_virtualmachine', 'shared_to_project')

        # Deleting field 'Network.shared_to_project'
        db.delete_column('db_network', 'shared_to_project')


    models = {
        'db.backend': {
            'Meta': {'ordering': "['clustername']", 'object_name': 'Backend'},
            'clustername': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            'ctotal': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'dfree': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'disk_templates': ('synnefo.db.fields.SeparatedValuesField', [], {'null': 'True'}),
            'drained': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'dtotal': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'hash': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'hypervisor': ('django.db.models.fields.CharField', [], {'default': "'kvm'", 'max_length': '32'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0', 'unique': 'True'}),
            'mfree': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'mtotal': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'offline': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'password_hash': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'pinst_cnt': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'port': ('django.db.models.fields.PositiveIntegerField', [], {'default': '5080'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'})
        },
        'db.backendnetwork': {
            'Meta': {'unique_together': "(('network', 'backend'),)", 'object_name': 'BackendNetwork'},
            'backend': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'networks'", 'on_delete': 'models.PROTECT', 'to': "orm['db.Backend']"}),
            'backendjobid': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'backendjobstatus': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'backendlogmsg': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'backendopcode': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'backendtime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1, 1, 1, 0, 0)'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mac_prefix': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'network': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'backend_networks'", 'on_delete': 'models.PROTECT', 'to': "orm['db.Network']"}),
            'operstate': ('django.db.models.fields.CharField', [], {'default': "'PENDING'", 'max_length': '30'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        'db.bridgepooltable': {
            'Meta': {'object_name': 'BridgePoolTable'},
            'available_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'base': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'offset': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'reserved_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'size': ('django.db.models.fields.IntegerField', [], {})
        },
        'db.flavor': {
            'Meta': {'unique_together': "(('cpu', 'ram', 'disk', 'volume_type'),)", 'object_name': 'Flavor'},
            'allow_create': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'cpu': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'disk': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ram': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'volume_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'flavors'", 'on_delete': 'models.PROTECT', 'to': "orm['db.VolumeType']"})
        },
        'db.image': {
            'Meta': {'unique_together': "(('uuid', 'version'),)", 'object_name': 'Image'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_snapshot': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_system': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'location': ('django.db.models.fields.TextField', [], {}),
            'mapfile': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'os': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'osfamily': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'uuid': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'version': ('django.db.models.fields.IntegerField', [], {})
        },
        'db.ipaddress': {
            'Meta': {'unique_together': "(('network', 'address', 'deleted'),)", 'object_name': 'IPAddress'},
            'address': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'floating_ip': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipversion': ('django.db.models.fields.IntegerField', [], {}),
            'network': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ips'", 'on_delete': 'models.PROTECT', 'to': "orm['db.Network']"}),
            'nic': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ips'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': "orm['db.NetworkInterface']"}),
            'project': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'serial': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ips'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': "orm['db.QuotaHolderSerial']"}),
            'shared_to_project': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'subnet': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ips'", 'on_delete': 'models.PROTECT', 'to': "orm['db.Subnet']"}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'userid': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'})
        },
        'db.ipaddresslog': {
            'Meta': {'object_name': 'IPAddressLog'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'address': ('django.db.models.fields.CharField', [], {'max_length': '64', 'db_index': 'True'}),
            'allocated_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'network_id': ('django.db.models.fields.IntegerField', [], {}),
            'released_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'server_id': ('django.db.models.fields.IntegerField', [], {})
        },
        'db.ippooltable': {
            'Meta': {'object_name': 'IPPoolTable'},
            'available_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'base': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'offset': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'reserved_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'size': ('django.db.models.fields.IntegerField', [], {}),
            'subnet': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ip_pools'", 'null': 'True', 'on_delete': 'models.PROTECT', 'to': "orm['db.Subnet']"})
        },
        'db.macprefixpooltable': {
            'Meta': {'object_name': 'MacPrefixPoolTable'},
            'available_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'base': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'offset': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'reserved_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'size': ('django.db.models.fields.IntegerField', [], {})
        },
        'db.network': {
            'Meta': {'object_name': 'Network'},
            'action': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '32', 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'drained': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'external_router': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'flavor': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'floating_ip_pool': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'link': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'mac_prefix': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'machines': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['db.VirtualMachine']", 'through': "orm['db.NetworkInterface']", 'symmetrical': 'False'}),
            'mode': ('django.db.models.fields.CharField', [], {'max_length': '16', 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'project': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'serial': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'network'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': "orm['db.QuotaHolderSerial']"}),
            'shared_to_project': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'PENDING'", 'max_length': '32'}),
            'subnet_ids': ('synnefo.db.fields.SeparatedValuesField', [], {'null': 'True'}),
            'tags': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'userid': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'db_index': 'True'})
        },
        'db.networkinterface': {
            'Meta': {'object_name': 'NetworkInterface'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'device_owner': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'firewall_profile': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'mac': ('django.db.models.fields.CharField', [], {'max_length': '32', 'unique': 'True', 'null': 'True'}),
            'machine': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'nics'", 'null': 'True', 'on_delete': 'models.PROTECT', 'to': "orm['db.VirtualMachine']"}),
            'name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128', 'null': 'True'}),
            'network': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'nics'", 'on_delete': 'models.PROTECT', 'to': "orm['db.Network']"}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'security_groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['db.SecurityGroup']", 'null': 'True', 'symmetrical': 'False'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'ACTIVE'", 'max_length': '32'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'userid': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'})
        },
        'db.quotaholderserial': {
            'Meta': {'ordering': "['serial']", 'object_name': 'QuotaHolderSerial'},
            'accept': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'pending': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'resolved': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'serial': ('django.db.models.fields.BigIntegerField', [], {'primary_key': 'True', 'db_index': 'True'})
        },
        'db.securitygroup': {
            'Meta': {'object_name': 'SecurityGroup'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'db.subnet': {
            'Meta': {'object_name': 'Subnet'},
            'cidr': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'dhcp': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'dns_nameservers': ('synnefo.db.fields.SeparatedValuesField', [], {'null': 'True'}),
            'gateway': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True'}),
            'host_routes': ('synnefo.db.fields.SeparatedValuesField', [], {'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipversion': ('django.db.models.fields.IntegerField', [], {'default': '4'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128', 'null': 'True'}),
            'network': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'subnets'", 'on_delete': 'models.PROTECT', 'to': "orm['db.Network']"}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'userid': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'db_index': 'True'})
        },
        'db.virtualmachine': {
            'Meta': {'object_name': 'VirtualMachine'},
            'action': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '30', 'null': 'True'}),
            'backend': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'virtual_machines'", 'null': 'True', 'on_delete': 'models.PROTECT', 'to': "orm['db.Backend']"}),
            'backend_hash': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'backendjobid': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'backendjobstatus': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'backendlogmsg': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'backendopcode': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'backendtime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1, 1, 1, 0, 0)'}),
            'buildpercentage': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'flavor': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['db.Flavor']", 'on_delete': 'models.PROTECT'}),
            'hostid': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_version': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'imageid': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'operstate': ('django.db.models.fields.CharField', [], {'default': "'BUILD'", 'max_length': '30'}),
            'project': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'serial': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'virtual_machine'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': "orm['db.QuotaHolderSerial']"}),
            'shared_to_project': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'suspended': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'task': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True'}),
            'task_job_id': ('django.db.models.fields.BigIntegerField', [], {'null': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'userid': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        },
        'db.virtualmachinediagnostic': {
            'Meta': {'ordering': "['-created']", 'object_name': 'VirtualMachineDiagnostic'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'details': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'machine': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'diagnostics'", 'to': "orm['db.VirtualMachine']"}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'source_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True'})
        },
        'db.virtualmachinemetadata': {
            'Meta': {'unique_together': "(('meta_key', 'vm'),)", 'object_name': 'VirtualMachineMetadata'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meta_key': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'meta_value': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'vm': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'metadata'", 'to': "orm['db.VirtualMachine']"})
        },
        'db.volume': {
            'Meta': {'object_name': 'Volume'},
            'backendjobid': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'delete_on_termination': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'machine': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'volumes'", 'null': 'True', 'to': "orm['db.VirtualMachine']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'origin': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'project': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'serial': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'volume'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': "orm['db.QuotaHolderSerial']"}),
            'shared_to_project': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'size': ('django.db.models.fields.IntegerField', [], {}),
            'snapshot_counter': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'source_version': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'CREATING'", 'max_length': '64'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'userid': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'}),
            'volume_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'volumes'", 'on_delete': 'models.PROTECT', 'to': "orm['db.VolumeType']"})
        },
        'db.volumemetadata': {
            'Meta': {'unique_together': "(('volume', 'key'),)", 'object_name': 'VolumeMetadata'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'volume': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'metadata'", 'to': "orm['db.Volume']"})
        },
        'db.volumetype': {
            'Meta': {'object_name': 'VolumeType'},
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'disk_template': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['db']