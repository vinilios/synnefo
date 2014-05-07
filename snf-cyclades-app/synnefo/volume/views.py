# Copyright (C) 2010-2014 GRNET S.A.
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

from itertools import ifilter
from logging import getLogger
from django.http import HttpResponse
from django.utils import simplejson as json
from django.utils.encoding import smart_unicode

from dateutil.parser import parse as date_parse

from snf_django.lib import api
from snf_django.lib.api import faults, utils

from synnefo.volume import volumes, snapshots, util
from synnefo.db.models import Volume, VolumeType
from synnefo.plankton.backend import PlanktonBackend

log = getLogger('synnefo.volume')


def display_null_field(field):
    if field is None:
        return None
    else:
        return smart_unicode(field)


def volume_to_dict(volume, detail=True):
    data = {
        "id": str(volume.id),
        "display_name": display_null_field(volume.name),
        "links": util.volume_to_links(volume.id),
    }
    if detail:
        details = {
            "status": volume.status.lower(),
            "size": volume.size,
            "display_description": volume.description,
            "created_at": utils.isoformat(volume.created),
            "metadata": dict((m.key, m.value) for m in volume.metadata.all()),
            "snapshot_id": display_null_field(volume.source_snapshot_id),
            "source_volid": display_null_field(volume.source_volume_id),
            "image_id": display_null_field(volume.source_image_id),
            "attachments": get_volume_attachments(volume),
            "volume_type": volume.volume_type_id,
            "delete_on_termination": volume.delete_on_termination,
            #"availabilit_zone": None,
            #"bootable": None,
            #"os-vol-tenant-attr:tenant_id": None,
            #"os-vol-host-attr:host": None,
            #"os-vol-mig-status-attr:name_id": None,
            #"os-vol-mig-status-attr:migstat": None,
        }
        data.update(details)
    return data


def get_volume_attachments(volume):
    if volume.machine_id is None:
        return []
    else:
        return [{"server_id": volume.machine_id,
                 "volume_id": volume.id,
                 "device_index": volume.index}]


@api.api_method(http_method="POST", user_required=True, logger=log)
def create_volume(request):
    """Create a new Volume."""

    req = utils.get_json_body(request)
    log.debug("create_volume %s", req)
    user_id = request.user_uniq

    vol_dict = utils.get_attribute(req, "volume", attr_type=dict,
                                   required=True)
    name = utils.get_attribute(vol_dict, "display_name",
                               attr_type=basestring, required=True)

    # Get and validate 'size' parameter
    size = utils.get_attribute(vol_dict, "size",
                               attr_type=(basestring, int), required=True)
    try:
        size = int(size)
        if size <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise faults.BadRequest("Volume 'size' needs to be a positive integer"
                                " value. '%s' cannot be accepted." % size)

    # Optional parameters
    volume_type_id = utils.get_attribute(vol_dict, "volume_type",
                                         attr_type=(basestring, int),
                                         required=False)
    description = utils.get_attribute(vol_dict, "display_description",
                                      attr_type=basestring, required=False,
                                      default="")
    metadata = utils.get_attribute(vol_dict, "metadata", attr_type=dict,
                                   required=False, default={})

    # Id of the volume to clone from
    source_volume_id = utils.get_attribute(vol_dict, "source_volid",
                                           required=False)
    # Id of the snapshot to create the volume from
    source_snapshot_id = utils.get_attribute(vol_dict, "snapshot_id",
                                             required=False)
    # Reference to an Image stored in Glance
    source_image_id = utils.get_attribute(vol_dict, "imageRef", required=False)

    # Get server ID to attach the volume. Since we currently do not supported
    # detached volumes, server_id attribute is mandatory.
    server_id = utils.get_attribute(vol_dict, "server_id", required=True)

    # Create the volume
    volume = volumes.create(user_id=user_id, size=size, name=name,
                            source_volume_id=source_volume_id,
                            source_snapshot_id=source_snapshot_id,
                            source_image_id=source_image_id,
                            volume_type_id=volume_type_id,
                            description=description,
                            metadata=metadata,
                            server_id=server_id)

    # Render response
    data = json.dumps(dict(volume=volume_to_dict(volume, detail=False)))
    return HttpResponse(data, status=202)


@api.api_method(http_method="GET", user_required=True, logger=log)
def list_volumes(request, detail=False):
    log.debug('list_volumes detail=%s', detail)
    volumes = Volume.objects.filter(userid=request.user_uniq)\
                            .prefetch_related("metadata")\
                            .order_by("id")

    volumes = utils.filter_modified_since(request, objects=volumes)

    volumes = [volume_to_dict(v, detail) for v in volumes]

    data = json.dumps({'volumes': volumes})
    return HttpResponse(data, content_type="application/json", status=200)


@api.api_method(http_method="DELETE", user_required=True, logger=log)
def delete_volume(request, volume_id):
    log.debug("delete_volume volume_id: %s", volume_id)

    volume = util.get_volume(request.user_uniq, volume_id, for_update=True)
    volumes.delete(volume)

    return HttpResponse(status=202)


@api.api_method(http_method="GET", user_required=True, logger=log)
def get_volume(request, volume_id):
    log.debug('get_volume volume_id: %s', volume_id)

    volume = util.get_volume(request.user_uniq, volume_id)

    data = json.dumps({'volume': volume_to_dict(volume, detail=True)})
    return HttpResponse(data, content_type="application/json", status=200)


@api.api_method(http_method="PUT", user_required=True, logger=log)
def update_volume(request, volume_id):
    req = utils.get_json_body(request)
    log.debug('update_volume volume_id: %s, request: %s', volume_id, req)

    volume = util.get_volume(request.user_uniq, volume_id, for_update=True)

    vol_req = utils.get_attribute(req, "volume", attr_type=dict,
                                  required=True)
    name = utils.get_attribute(vol_req, "display_name", required=False)
    description = utils.get_attribute(vol_req, "display_description",
                                      required=False)
    delete_on_termination = utils.get_attribute(vol_req,
                                                "delete_on_termination",
                                                attr_type=bool,
                                                required=False)

    if name is None and description is None and\
       delete_on_termination is None:
        raise faults.BadRequest("Nothing to update.")
    else:
        volume = volumes.update(volume, name, description,
                                delete_on_termination)

    data = json.dumps({'volume': volume_to_dict(volume, detail=True)})
    return HttpResponse(data, content_type="application/json", status=200)


def snapshot_to_dict(snapshot, detail=True):
    owner = snapshot['owner']
    status = snapshot['status']
    progress = "%s%%" % 100 if status == "AVAILABLE" else 0

    data = {
        "id": snapshot["id"],
        "size": int(snapshot["size"]) >> 30,  # gigabytes
        "display_name": snapshot["name"],
        "display_description": snapshot.get("description", ""),
        "status": status,
        "user_id": owner,
        "tenant_id": owner,
        "os-extended-snapshot-attribute:progress": progress,
        #"os-extended-snapshot-attribute:project_id": project,
        "created_at": utils.isoformat(date_parse(snapshot["created_at"])),
        "metadata": snapshot.get("metadata", {}),
        "volume_id": snapshot.get("volume_id"),
        "links": util.snapshot_to_links(snapshot["id"])
    }
    return data


@api.api_method(http_method="POST", user_required=True, logger=log)
def create_snapshot(request):
    """Create a new Snapshot."""

    req = utils.get_json_body(request)
    log.debug("create_snapshot %s", req)
    user_id = request.user_uniq

    snap_dict = utils.get_attribute(req, "snapshot", required=True,
                                    attr_type=dict)
    volume_id = utils.get_attribute(snap_dict, "volume_id", required=True)
    volume = util.get_volume(user_id, volume_id, for_update=True,
                             exception=faults.BadRequest)

    metadata = utils.get_attribute(snap_dict, "metadata", required=False,
                                   attr_type=dict, default={})
    name = utils.get_attribute(snap_dict, "display_name", required=False,
                               attr_type=basestring,
                               default="Snapshot of volume '%s'" % volume_id)
    description = utils.get_attribute(snap_dict, "display_description",
                                      required=False,
                                      attr_type=basestring, default="")

    # TODO: What to do with force ?
    force = utils.get_attribute(req, "force", required=False, attr_type=bool,
                                default=False)

    snapshot = snapshots.create(user_id=user_id, volume=volume, name=name,
                                description=description, metadata=metadata,
                                force=force)

    # Render response
    data = json.dumps(dict(snapshot=snapshot_to_dict(snapshot, detail=False)))
    return HttpResponse(data, status=202)


@api.api_method(http_method="GET", user_required=True, logger=log)
def list_snapshots(request, detail=False):
    log.debug('list_snapshots detail=%s', detail)
    since = utils.isoparse(request.GET.get('changes-since'))
    with PlanktonBackend(request.user_uniq) as backend:
        snapshots = backend.list_snapshots()
        if since:
            updated_since = lambda snap:\
                date_parse(snap["updated_at"]) >= since
            snapshots = ifilter(updated_since, snapshots)
            if not snapshots:
                return HttpResponse(status=304)

    snapshots = sorted(snapshots, key=lambda x: x['id'])
    snapshots_dict = [snapshot_to_dict(snapshot, detail)
                      for snapshot in snapshots]

    data = json.dumps(dict(snapshots=snapshots_dict))

    return HttpResponse(data, status=200)


@api.api_method(http_method="DELETE", user_required=True, logger=log)
def delete_snapshot(request, snapshot_id):
    log.debug("delete_snapshot snapshot_id: %s", snapshot_id)

    snapshot = util.get_snapshot(request.user_uniq, snapshot_id)
    snapshots.delete(snapshot)

    return HttpResponse(status=202)


@api.api_method(http_method="GET", user_required=True, logger=log)
def get_snapshot(request, snapshot_id):
    log.debug('get_snapshot snapshot_id: %s', snapshot_id)

    snapshot = util.get_snapshot(request.user_uniq, snapshot_id)
    data = json.dumps({'snapshot': snapshot_to_dict(snapshot, detail=True)})
    return HttpResponse(data, content_type="application/json", status=200)


@api.api_method(http_method="PUT", user_required=True, logger=log)
def update_snapshot(request, snapshot_id):
    req = utils.get_json_body(request)
    log.debug('update_snapshot snapshot_id: %s, request: %s', snapshot_id, req)
    snapshot = util.get_snapshot(request.user_uniq, snapshot_id)

    snap_dict = utils.get_attribute(req, "snapshot", attr_type=dict,
                                    required=True)
    new_name = utils.get_attribute(snap_dict, "display_name", required=False,
                                   attr_type=basestring)
    new_description = utils.get_attribute(snap_dict, "display_description",
                                          required=False, attr_type=basestring)

    if new_name is None and new_description is None:
        raise faults.BadRequest("Nothing to update.")

    snapshot = snapshots.update(snapshot, name=new_name,
                                description=new_description)

    data = json.dumps({'snapshot': snapshot_to_dict(snapshot, detail=True)})
    return HttpResponse(data, content_type="application/json", status=200)


def volume_type_to_dict(volume_type):
    vtype_info = {
        "id": volume_type.id,
        "name": volume_type.name,
        "deleted": volume_type.deleted,
        "SNF:disk_template": volume_type.disk_template}
    return vtype_info


@api.api_method(http_method="GET", user_required=True, logger=log)
def list_volume_types(request):
    log.debug('list_volumes')
    vtypes = VolumeType.objects.filter(deleted=False).order_by("id")
    vtypes = [volume_type_to_dict(vtype) for vtype in vtypes]
    data = json.dumps({'volume_types': vtypes})
    return HttpResponse(data, content_type="application/json", status=200)


@api.api_method(http_method="GET", user_required=True, logger=log)
def get_volume_type(request, volume_type_id):
    log.debug('get_volume_type volume_type_id: %s', volume_type_id)
    volume_type = util.get_volume_type(volume_type_id, include_deleted=True)
    data = json.dumps({'volume_type': volume_type_to_dict(volume_type)})
    return HttpResponse(data, content_type="application/json", status=200)
