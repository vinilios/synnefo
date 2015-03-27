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

import uuid
import logging
import json
import copy

from datetime import datetime, timedelta
import base64
from urllib import quote
from random import randint
import os

from django.db import models
from astakos.im import transaction
from django.contrib.auth.models import User, UserManager, Group, Permission
from django.utils.translation import ugettext as _
from django.db.models.signals import pre_save, post_save
from django.contrib.contenttypes.models import ContentType

from django.db.models import Q
from django.core.urlresolvers import reverse
from django.utils.http import int_to_base36
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.utils.importlib import import_module
from django.utils.safestring import mark_safe

from synnefo.lib.utils import dict_merge

from astakos.im import settings as astakos_settings
from astakos.im import auth_providers as auth

import astakos.im.messages as astakos_messages
from synnefo.lib.ordereddict import OrderedDict

from synnefo.util import units
from astakos.im import presentation

logger = logging.getLogger(__name__)

DEFAULT_CONTENT_TYPE = None
_content_type = None

SYSTEM_PROJECT_NAME_TPL = getattr(astakos_settings, "SYSTEM_PROJECT_NAME_TPL",
                                u"[system] %s")


def get_content_type():
    global _content_type
    if _content_type is not None:
        return _content_type

    try:
        content_type = ContentType.objects.get(app_label='im',
                                               model='astakosuser')
    except:
        content_type = DEFAULT_CONTENT_TYPE
    _content_type = content_type
    return content_type

inf = float('inf')


def generate_token():
    s = os.urandom(32)
    return base64.urlsafe_b64encode(s).rstrip('=')


def _partition_by(f, l):
    d = {}
    for x in l:
        group = f(x)
        group_l = d.get(group, [])
        group_l.append(x)
        d[group] = group_l
    return d


def first_of_group(f, l):
    Nothing = type("Nothing", (), {})
    last_group = Nothing
    d = {}
    for x in l:
        group = f(x)
        if group != last_group:
            last_group = group
            d[group] = x
    return d


class Component(models.Model):
    name = models.CharField(_('Name'), max_length=255, unique=True,
                            db_index=True)
    url = models.CharField(_('Component url'), max_length=1024, null=True,
                           help_text=_("URL the component is accessible from"))
    base_url = models.CharField(max_length=1024, null=True)
    auth_token = models.CharField(_('Authentication Token'), max_length=64,
                                  null=True, blank=True, unique=True)
    auth_token_created = models.DateTimeField(_('Token creation date'),
                                              null=True)
    auth_token_expires = models.DateTimeField(_('Token expiration date'),
                                              null=True)

    def renew_token(self, expiration_date=None):
        for i in range(10):
            new_token = generate_token()
            count = Component.objects.filter(auth_token=new_token).count()
            if count == 0:
                break
            continue
        else:
            raise ValueError('Could not generate a token')

        self.auth_token = new_token
        self.auth_token_created = datetime.now()
        if expiration_date:
            self.auth_token_expires = expiration_date
        else:
            self.auth_token_expires = None
        msg = 'Token renewed for component %s'
        logger.log(astakos_settings.LOGGING_LEVEL, msg, self.name)

    def __unicode__(self):
        return self.name

    @classmethod
    def catalog(cls, orderfor=None):
        catalog = {}
        components = list(cls.objects.all())
        default_metadata = presentation.COMPONENTS
        metadata = {}

        for component in components:
            d = {'url': component.url,
                 'name': component.name}
            if component.name in default_metadata:
                metadata[component.name] = default_metadata.get(component.name)
                metadata[component.name].update(d)
            else:
                metadata[component.name] = d

        def component_by_order(s):
            return s[1].get('order')

        def component_by_dashboard_order(s):
            return s[1].get('dashboard').get('order')

        metadata = dict_merge(metadata,
                              astakos_settings.COMPONENTS_META)

        for component, info in metadata.iteritems():
            default_meta = presentation.component_defaults(component)
            base_meta = metadata.get(component, {})
            settings_meta = astakos_settings.COMPONENTS_META.get(component, {})
            component_meta = dict_merge(default_meta, base_meta)
            meta = dict_merge(component_meta, settings_meta)
            catalog[component] = meta

        order_key = component_by_order
        if orderfor == 'dashboard':
            order_key = component_by_dashboard_order

        ordered_catalog = OrderedDict(sorted(catalog.iteritems(),
                                             key=order_key))
        return ordered_catalog


_presentation_data = {}


def get_presentation(resource):
    global _presentation_data
    resource_presentation = _presentation_data.get(resource, {})
    if not resource_presentation:
        resources_presentation = presentation.RESOURCES.get('resources', {})
        resource_presentation = resources_presentation.get(resource, {})
        _presentation_data[resource] = resource_presentation
    return resource_presentation


class Service(models.Model):
    component = models.ForeignKey(Component)
    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=255)


class Endpoint(models.Model):
    service = models.ForeignKey(Service, related_name='endpoints')


class EndpointData(models.Model):
    endpoint = models.ForeignKey(Endpoint, related_name='data')
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=1024)

    class Meta:
        unique_together = (('endpoint', 'key'),)


class Resource(models.Model):
    name = models.CharField(_('Name'), max_length=255, unique=True)
    desc = models.TextField(_('Description'), null=True)
    service_type = models.CharField(_('Type'), max_length=255)
    service_origin = models.CharField(max_length=255, db_index=True)
    unit = models.CharField(_('Unit'), null=True, max_length=255)
    uplimit = models.BigIntegerField(default=0)
    project_default = models.BigIntegerField()
    ui_visible = models.BooleanField(default=True)
    api_visible = models.BooleanField(default=True)

    def __unicode__(self):
        return self.name

    def full_name(self):
        return unicode(self)

    def get_info(self):
        return {'service': self.service_origin,
                'description': self.desc,
                'unit': self.unit,
                'ui_visible': self.ui_visible,
                'api_visible': self.api_visible,
                }

    @property
    def group(self):
        default = self.name
        return get_presentation(unicode(self)).get('group', default)

    @property
    def help_text(self):
        default = "%s resource" % self.name
        return get_presentation(unicode(self)).get('help_text', default)

    @property
    def help_text_input_each(self):
        default = "%s resource" % self.name
        return get_presentation(unicode(self)).get(
            'help_text_input_each', default)

    @property
    def help_text_input_total(self):
        default = "%s resource" % self.name
        key = 'help_text_input_total'
        return get_presentation(str(self)).get(key, default)

    @property
    def is_abbreviation(self):
        return get_presentation(unicode(self)).get('is_abbreviation', False)

    @property
    def report_desc(self):
        default = "%s resource" % self.name
        return get_presentation(unicode(self)).get('report_desc', default)

    @property
    def placeholder(self):
        return get_presentation(unicode(self)).get('placeholder', self.unit)

    @property
    def verbose_name(self):
        return get_presentation(unicode(self)).get('verbose_name', self.name)

    @property
    def display_name(self):
        name = self.verbose_name
        if self.is_abbreviation:
            name = name.upper()
        return name

    @property
    def pluralized_display_name(self):
        if not self.unit:
            return '%ss' % self.display_name
        return self.display_name


def get_resource_names():
    _RESOURCE_NAMES = []
    resources = Resource.objects.select_related('service').all()
    _RESOURCE_NAMES = [resource.full_name() for resource in resources]
    return _RESOURCE_NAMES


def split_realname(value):
    parts = value.split(' ')
    if len(parts) == 2:
        return parts
    else:
        return ('', value)


class AstakosUserManager(UserManager):

    def get_auth_provider_user(self, provider, **kwargs):
        """
        Retrieve AstakosUser instance associated with the specified third party
        id.
        """
        kwargs = dict(map(lambda x: ('auth_providers__%s' % x[0], x[1]),
                          kwargs.iteritems()))
        return self.get(auth_providers__module=provider, **kwargs)

    def get_by_email(self, email):
        return self.get(email=email)

    def get_by_identifier(self, email_or_username, **kwargs):
        try:
            return self.get(email__iexact=email_or_username, **kwargs)
        except AstakosUser.DoesNotExist:
            return self.get(username__iexact=email_or_username, **kwargs)

    def user_exists(self, email_or_username, **kwargs):
        qemail = Q(email__iexact=email_or_username)
        qusername = Q(username__iexact=email_or_username)
        qextra = Q(**kwargs)
        return self.filter((qemail | qusername) & qextra).exists()

    def unverified_namesakes(self, email_or_username):
        q = Q(email__iexact=email_or_username)
        q |= Q(username__iexact=email_or_username)
        return self.filter(q & Q(email_verified=False))

    def verified_user_exists(self, email_or_username):
        return self.user_exists(email_or_username, email_verified=True)

    def verified(self):
        return self.filter(email_verified=True)

    def accepted(self):
        return self.filter(moderated=True, is_rejected=False)

    def uuid_catalog(self, l=None):
        """
        Returns a uuid to username mapping for the uuids appearing in l.
        If l is None returns the mapping for all existing users.
        """
        q = self.filter(uuid__in=l) if l is not None else self
        return dict(q.values_list('uuid', 'username'))

    def displayname_catalog(self, l=None):
        """
        Returns a username to uuid mapping for the usernames appearing in l.
        If l is None returns the mapping for all existing users.
        """
        if l is not None:
            lmap = dict((x.lower(), x) for x in l)
            q = self.filter(username__in=lmap.keys())
            values = ((lmap[n], u)
                      for n, u in q.values_list('username', 'uuid'))
        else:
            q = self
            values = self.values_list('username', 'uuid')
        return dict(values)


class AstakosUser(User):
    """
    Extends ``django.contrib.auth.models.User`` by defining additional fields.
    """
    affiliation = models.CharField(_('Affiliation'), max_length=255,
                                   blank=True, null=True)

    #for invitations
    user_level = astakos_settings.DEFAULT_USER_LEVEL
    level = models.IntegerField(_('Inviter level'), default=user_level)
    invitations = models.IntegerField(
        _('Invitations left'),
        default=astakos_settings.INVITATIONS_PER_LEVEL.get(user_level, 0))

    auth_token = models.CharField(
        _('Authentication Token'),
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        help_text=_('Renew your authentication '
                    'token. Make sure to set the new '
                    'token in any client you may be '
                    'using, to preserve its '
                    'functionality.'))
    auth_token_created = models.DateTimeField(_('Token creation date'),
                                              null=True)
    auth_token_expires = models.DateTimeField(
        _('Token expiration date'), null=True)

    updated = models.DateTimeField(_('Last update date'))

    # Arbitrary text to identify the reason user got deactivated.
    # To be used as a reference from administrators.
    deactivated_reason = models.TextField(
        _('Reason for user deactivation'),
        default=None, null=True)
    deactivated_at = models.DateTimeField(_('User deactivation date'),
                                          null=True,
                                          blank=True)

    has_credits = models.BooleanField(_('User has credits'), default=False)

    # this is set to True when user profile gets updated for the first time
    is_verified = models.BooleanField(_('User is verified'), default=False)

    # user email is verified
    email_verified = models.BooleanField(_('User email is verified'),
                                         default=False)

    # unique string used in user email verification url
    verification_code = models.CharField(
        _('String used for email verification'),
        max_length=255, null=True,
        blank=False, unique=True)

    # date user email verified
    verified_at = models.DateTimeField(_('User verification date'), null=True,
                                       blank=True)

    # email verification notice was sent to the user at this time
    activation_sent = models.DateTimeField(_('Activation sent date'),
                                           null=True, blank=True)

    # user got rejected during moderation process
    is_rejected = models.BooleanField(_('Account is rejected'),
                                      default=False)
    # reason user got rejected
    rejected_reason = models.TextField(_('Reason for user rejection'),
                                       null=True,
                                       blank=True)
    # moderation status
    moderated = models.BooleanField(_('Account is moderated'), default=False)
    # date user moderated (either accepted or rejected)
    moderated_at = models.DateTimeField(_('Date moderated'), default=None,
                                        blank=True, null=True)
    # a snapshot of user instance the time got moderated
    moderated_data = models.TextField(null=True, default=None, blank=True)
    # a string which identifies how the user got moderated
    accepted_policy = models.CharField(_('Accepted policy'), max_length=255,
                                       default=None, null=True, blank=True)
    # the email used to accept the user
    accepted_email = models.EmailField(null=True, default=None, blank=True)

    has_signed_terms = models.BooleanField(_('False if needs to sign terms'),
                                           default=False)
    date_signed_terms = models.DateTimeField(_('Date of terms signing'),
                                             null=True, blank=True)
    # permanent unique user identifier
    uuid = models.CharField(_('Unique user identifier'),
                            max_length=255, null=False, blank=False,
                            unique=True)

    policy = models.ManyToManyField(
        Resource, null=True, through='AstakosUserQuota')

    disturbed_quota = models.BooleanField(_('Needs quotaholder syncing'),
                                          default=False, db_index=True)

    # This could have been OneToOneField, but fails due to
    # https://code.djangoproject.com/ticket/13781 (fixed in v1.6)
    base_project = models.ForeignKey('Project', related_name="base_user",
                                     null=True)

    objects = AstakosUserManager()

    @property
    def realname(self):
        return '%s %s' % (self.first_name, self.last_name)

    @property
    def realname_with_email(self):
        return '%s (%s)' % (self.realname, self.email)

    @property
    def log_display(self):
        """
        Should be used in all logger.* calls that refer to a user so that
        user display is consistent across log entries.
        """
        return '%s::%s' % (self.uuid, self.email)

    @realname.setter
    def realname(self, value):
        first, last = split_realname(value)
        self.first_name = first
        self.last_name = last

    def get_base_project(self):
        assert self.base_project is not None, \
            "User %s has no system project" % self
        return self.base_project

    def add_permission(self, pname):
        if self.has_perm(pname):
            return
        p, created = Permission.objects.get_or_create(
            codename=pname,
            name=pname.capitalize(),
            content_type=get_content_type())
        self.user_permissions.add(p)

    def remove_permission(self, pname):
        if self.has_perm(pname):
            return
        p = Permission.objects.get(codename=pname,
                                   content_type=get_content_type())
        self.user_permissions.remove(p)

    def add_group(self, gname):
        group, _ = Group.objects.get_or_create(name=gname)
        self.groups.add(group)

    def is_accepted(self):
        return self.moderated and not self.is_rejected

    def is_project_admin(self):
        return self.uuid in astakos_settings.PROJECT_ADMINS

    @property
    def invitation(self):
        try:
            return Invitation.objects.get(username=self.email)
        except Invitation.DoesNotExist:
            return None

    @property
    def policies(self):
        return self.astakosuserquota_set.select_related().all()

    def get_resource_policy(self, resource):
        return AstakosUserQuota.objects.select_related("resource").\
            get(user=self, resource__name=resource)

    def fix_username(self):
        self.username = self.email.lower()

    def set_email(self, email):
        self.email = email
        self.fix_username()

    def save(self, update_timestamps=True, **kwargs):
        if update_timestamps:
            self.updated = datetime.now()

        super(AstakosUser, self).save(**kwargs)

    def renew_verification_code(self):
        self.verification_code = str(uuid.uuid4())
        logger.info("Verification code renewed for %s" % self.log_display)

    def renew_token(self, flush_sessions=False, current_key=None):
        for i in range(10):
            new_token = generate_token()
            count = AstakosUser.objects.filter(auth_token=new_token).count()
            if count == 0:
                break
            continue
        else:
            raise ValueError('Could not generate a token')

        self.auth_token = new_token
        self.auth_token_created = datetime.now()
        self.auth_token_expires = self.auth_token_created + \
            timedelta(hours=astakos_settings.AUTH_TOKEN_DURATION)
        if flush_sessions:
            self.flush_sessions(current_key)
        self.delete_online_access_tokens()
        msg = 'Token renewed for %s'
        logger.log(astakos_settings.LOGGING_LEVEL, msg, self.log_display)

    def token_expired(self):
        return self.auth_token_expires < datetime.now()

    def flush_sessions(self, current_key=None):
        q = self.sessions
        if current_key:
            q = q.exclude(session_key=current_key)

        keys = q.values_list('session_key', flat=True)
        if keys:
            msg = 'Flushing sessions: %s'
            logger.log(astakos_settings.LOGGING_LEVEL, msg, ','.join(keys))
        engine = import_module(settings.SESSION_ENGINE)
        for k in keys:
            s = engine.SessionStore(k)
            s.flush()

    def __unicode__(self):
        return '%s (%s)' % (self.realname, self.email)

    def conflicting_email(self):
        q = AstakosUser.objects.exclude(username=self.username)
        q = q.filter(email__iexact=self.email)
        if q.count() != 0:
            return True
        return False

    def email_change_is_pending(self):
        return self.emailchanges.count() > 0

    @property
    def status_display(self):
        if not self.email_verified:
            msg = "Pending email verification"
        elif not self.moderated:
            msg = "Pending moderation"
        elif self.is_rejected:
            msg = "Rejected"
            if self.rejected_reason:
                msg += " (%s)" % self.rejected_reason
        # accepted
        else:
            if self.is_active:
                msg = "Accepted/Active"
            else:
                msg = "Accepted/Inactive"
                if self.deactivated_reason:
                    msg += " (%s)" % (self.deactivated_reason)
            if self.accepted_policy == 'manual':
                msg += " (manually accepted)"
            else:
                msg += " (accepted policy: %s)" % \
                    self.accepted_policy
        return msg

    @property
    def signed_terms(self):
        return self.has_signed_terms

    def set_invitations_level(self):
        """
        Update user invitation level
        """
        level = self.invitation.inviter.level + 1
        self.level = level
        self.invitations = astakos_settings.INVITATIONS_PER_LEVEL.get(level, 0)

    def can_change_password(self):
        return self.has_auth_provider('local', auth_backend='astakos')

    def can_change_email(self):
        if not self.has_auth_provider('local'):
            return True

        local = self.get_auth_provider('local')._instance
        return local.auth_backend == 'astakos'

    # Auth providers related methods
    def get_auth_provider(self, module=None, identifier=None, **filters):
        if not module:
            return self.auth_providers.active()[0].settings

        params = {'module': module}
        if identifier:
            params['identifier'] = identifier
        params.update(filters)
        return self.auth_providers.active().get(**params).settings

    def has_auth_provider(self, provider, **kwargs):
        return bool(self.auth_providers.active().filter(module=provider,
                                                        **kwargs).count())

    def get_required_providers(self, **kwargs):
        return auth.REQUIRED_PROVIDERS.keys()

    def missing_required_providers(self):
        required = self.get_required_providers()
        missing = []
        for provider in required:
            if not self.has_auth_provider(provider):
                missing.append(auth.get_provider(provider, self))
        return missing

    def get_available_auth_providers(self, **filters):
        """
        Returns a list of providers available for add by the user.
        """
        modules = astakos_settings.IM_MODULES
        providers = []
        for p in modules:
            providers.append(auth.get_provider(p, self))
        available = []

        for p in providers:
            if p.get_add_policy:
                available.append(p)
        return available

    def get_disabled_auth_providers(self, **filters):
        providers = self.get_auth_providers(**filters)
        disabled = []
        for p in providers:
            if not p.get_login_policy:
                disabled.append(p)
        return disabled

    def get_enabled_auth_providers(self, **filters):
        providers = self.get_auth_providers(**filters)
        enabled = []
        for p in providers:
            if p.get_login_policy:
                enabled.append(p)
        return enabled

    def get_auth_providers(self, **filters):
        providers = []
        for provider in self.auth_providers.active(**filters):
            if provider.settings.module_enabled:
                providers.append(provider.settings)

        modules = astakos_settings.IM_MODULES

        def key(p):
            if not p.module in modules:
                return 100
            return modules.index(p.module)

        providers = sorted(providers, key=key)
        return providers

    # URL methods
    @property
    def auth_providers_display(self):
        return ",".join(["%s:%s" % (p.module, p.identifier or '') for p in
                         self.get_enabled_auth_providers()])

    def add_auth_provider(self, module='local', identifier=None, **params):
        provider = auth.get_provider(module, self, identifier, **params)
        provider.add_to_user()

    def get_resend_activation_url(self):
        return reverse('send_activation', urlconf="synnefo.webproject.urls",
                       kwargs={'user_id': self.pk})

    def get_activation_url(self, nxt=False):
        activate_url = reverse('astakos.im.views.activate',
                               urlconf="synnefo.webproject.urls")
        url = "%s?auth=%s" % (activate_url, quote(self.verification_code))
        if nxt:
            url += "&next=%s" % quote(nxt)
        return url

    def get_password_reset_url(self, token_generator=default_token_generator):
        return reverse('astakos.im.views.target.local.password_reset_confirm',
                       urlconf="synnefo.webproject.urls",
                       kwargs={'uidb36': int_to_base36(self.id),
                               'token': token_generator.make_token(self)})

    def get_inactive_message(self, provider_module, identifier=None):
        try:
            provider = self.get_auth_provider(provider_module, identifier)
        except AstakosUserAuthProvider.DoesNotExist:
            provider = auth.get_provider(provider_module, self)

        msg_extra = ''
        message = ''

        msg_inactive = provider.get_account_inactive_msg
        msg_pending = provider.get_pending_activation_msg
        msg_pending_help = _(astakos_messages.ACCOUNT_PENDING_ACTIVATION_HELP)
        #msg_resend_prompt = _(astakos_messages.ACCOUNT_RESEND_ACTIVATION)
        msg_pending_mod = provider.get_pending_moderation_msg
        msg_rejected = _(astakos_messages.ACCOUNT_REJECTED)
        msg_resend = _(astakos_messages.ACCOUNT_RESEND_ACTIVATION)

        if not self.email_verified:
            message = msg_pending
            url = self.get_resend_activation_url()
            msg_extra = msg_pending_help + \
                u' ' + \
                '<a href="%s">%s?</a>' % (url, msg_resend)
        else:
            if not self.moderated:
                message = msg_pending_mod
            else:
                if self.is_rejected:
                    message = msg_rejected
                else:
                    message = msg_inactive

        return mark_safe(message + u' ' + msg_extra)

    def owns_application(self, application):
        return application.owner == self

    def owns_project(self, project):
        return project.owner == self

    def is_associated(self, project):
        try:
            m = ProjectMembership.objects.get(person=self, project=project)
            return m.state in ProjectMembership.ASSOCIATED_STATES
        except ProjectMembership.DoesNotExist:
            return False

    def get_membership(self, project):
        try:
            return ProjectMembership.objects.get(
                project=project,
                person=self)
        except ProjectMembership.DoesNotExist:
            return None

    def membership_display(self, project):
        m = self.get_membership(project)
        if m is None:
            return _('Not a member')
        else:
            return m.user_friendly_state_display()

    def non_owner_can_view(self, maybe_project):
        if self.is_project_admin():
            return True
        if maybe_project is None:
            return False
        project = maybe_project
        if self.is_associated(project):
            return True
        if project.is_deactivated():
            return False
        return True

    def delete_online_access_tokens(self):
        offline_tokens = self.token_set.filter(access_token='online')
        logger.info('The following access tokens will be deleted: %s',
                    offline_tokens)
        offline_tokens.delete()

    def get_last_logins(self):
        providers = self.auth_providers.filter().order_by('-last_login_at')
        providers = providers.filter(last_login_at__isnull=False)
        logins = []
        for provider in providers:
            logins.append((provider.module, provider.last_login_at))

        return logins

    @property
    def last_login_info_display(self):
        logins = self.get_last_logins()
        display = []

        if len(logins) == 0:
            return "No login info available"

        for module, date in logins:
            display.append("[%s] %s" % (module, date))

        return ", ".join(display)



class AstakosUserAuthProviderManager(models.Manager):

    def active(self, **filters):
        return self.filter(active=True, **filters)

    def remove_unverified_providers(self, provider, **filters):
        try:
            existing = self.filter(module=provider, user__email_verified=False,
                                   **filters)
            for p in existing:
                p.user.delete()
        except:
            pass

    def unverified(self, provider, **filters):
        try:

            return self.select_for_update().get(module=provider,
                                                user__email_verified=False,
                                                **filters).settings
        except AstakosUserAuthProvider.DoesNotExist:
            return None

    def verified(self, provider, **filters):
        try:
            return self.get(module=provider, user__email_verified=True,
                            **filters).settings
        except AstakosUserAuthProvider.DoesNotExist:
            return None


class AuthProviderPolicyProfileManager(models.Manager):

    def active(self):
        return self.filter(active=True)

    def for_user(self, user, provider):
        policies = {}
        exclusive_q1 = Q(provider=provider) & Q(is_exclusive=False)
        exclusive_q2 = ~Q(provider=provider) & Q(is_exclusive=True)
        exclusive_q = exclusive_q1 | exclusive_q2

        for profile in user.authpolicy_profiles.active().filter(exclusive_q):
            policies.update(profile.policies)

        user_groups = user.groups.all().values('pk')
        for profile in self.active().filter(groups__in=user_groups).filter(
                exclusive_q):
            policies.update(profile.policies)
        return policies

    def add_policy(self, name, provider, group_or_user, exclusive=False,
                   **policies):
        is_group = isinstance(group_or_user, Group)
        profile, created = self.get_or_create(name=name, provider=provider,
                                              is_exclusive=exclusive)
        profile.is_exclusive = exclusive
        profile.save()
        if is_group:
            profile.groups.add(group_or_user)
        else:
            profile.users.add(group_or_user)
        profile.set_policies(policies)
        profile.save()
        return profile


class AuthProviderPolicyProfile(models.Model):
    name = models.CharField(_('Name'), max_length=255, blank=False,
                            null=False, db_index=True)
    provider = models.CharField(_('Provider'), max_length=255, blank=False,
                                null=False)

    # apply policies to all providers excluding the one set in provider field
    is_exclusive = models.BooleanField(default=False)

    policy_add = models.NullBooleanField(null=True, default=None)
    policy_remove = models.NullBooleanField(null=True, default=None)
    policy_create = models.NullBooleanField(null=True, default=None)
    policy_login = models.NullBooleanField(null=True, default=None)
    policy_limit = models.IntegerField(null=True, default=None)
    policy_required = models.NullBooleanField(null=True, default=None)
    policy_automoderate = models.NullBooleanField(null=True, default=None)
    policy_switch = models.NullBooleanField(null=True, default=None)

    POLICY_FIELDS = ('add', 'remove', 'create', 'login', 'limit', 'required',
                     'automoderate')

    priority = models.IntegerField(null=False, default=1)
    groups = models.ManyToManyField(Group, related_name='authpolicy_profiles')
    users = models.ManyToManyField(AstakosUser,
                                   related_name='authpolicy_profiles')
    active = models.BooleanField(default=True)

    objects = AuthProviderPolicyProfileManager()

    class Meta:
        ordering = ['priority']

    @property
    def policies(self):
        policies = {}
        for pkey in self.POLICY_FIELDS:
            value = getattr(self, 'policy_%s' % pkey, None)
            if value is None:
                continue
            policies[pkey] = value
        return policies

    def set_policies(self, policies_dict):
        for key, value in policies_dict.iteritems():
            if key in self.POLICY_FIELDS:
                setattr(self, 'policy_%s' % key, value)
        return self.policies


class AstakosUserAuthProvider(models.Model):
    """
    Available user authentication methods.
    """
    affiliation = models.CharField(_('Affiliation'), max_length=255,
                                   blank=True, null=True, default=None)
    user = models.ForeignKey(AstakosUser, related_name='auth_providers')
    module = models.CharField(_('Provider'), max_length=255, blank=False,
                              default='local')
    identifier = models.CharField(_('Third-party identifier'),
                                  max_length=255, null=True,
                                  blank=True)
    active = models.BooleanField(default=True)
    auth_backend = models.CharField(_('Backend'), max_length=255, blank=False,
                                    default='astakos')
    info_data = models.TextField(default="", null=True, blank=True)
    created = models.DateTimeField('Creation date', auto_now_add=True)
    last_login_at = models.DateTimeField('Last login date', null=True,
                                         default=None)

    objects = AstakosUserAuthProviderManager()

    class Meta:
        unique_together = (('identifier', 'module', 'user'), )
        ordering = ('module', 'created')

    def __init__(self, *args, **kwargs):
        super(AstakosUserAuthProvider, self).__init__(*args, **kwargs)
        try:
            self.info = json.loads(self.info_data)
            if not self.info:
                self.info = {}
        except Exception:
            self.info = {}

        for key, value in self.info.iteritems():
            setattr(self, 'info_%s' % key, value)

    @property
    def settings(self):
        extra_data = {}

        info_data = {}
        if self.info_data:
            info_data = json.loads(self.info_data)

        extra_data['info'] = info_data

        for key in ['active', 'auth_backend', 'created', 'pk', 'affiliation']:
            extra_data[key] = getattr(self, key)

        extra_data['instance'] = self
        return auth.get_provider(self.module, self.user,
                                 self.identifier, **extra_data)

    def __repr__(self):
        return '<AstakosUserAuthProvider %s:%s>' % (
            self.module, self.identifier)

    def __unicode__(self):
        if self.identifier:
            return "%s:%s" % (self.module, self.identifier)
        if self.auth_backend:
            return "%s:%s" % (self.module, self.auth_backend)
        return self.module

    def save(self, *args, **kwargs):
        self.info_data = json.dumps(self.info)
        return super(AstakosUserAuthProvider, self).save(*args, **kwargs)


class AstakosUserQuota(models.Model):
    capacity = models.BigIntegerField()
    resource = models.ForeignKey(Resource)
    user = models.ForeignKey(AstakosUser)

    class Meta:
        unique_together = ("resource", "user")


class ApprovalTerms(models.Model):
    """
    Model for approval terms
    """

    date = models.DateTimeField(
        _('Issue date'), db_index=True, auto_now_add=True)
    location = models.CharField(_('Terms location'), max_length=255)


class Invitation(models.Model):
    """
    Model for registring invitations
    """
    inviter = models.ForeignKey(AstakosUser, related_name='invitations_sent',
                                null=True)
    realname = models.CharField(_('Real name'), max_length=255)
    username = models.CharField(_('Unique ID'), max_length=255, unique=True)
    code = models.BigIntegerField(_('Invitation code'), db_index=True)
    is_consumed = models.BooleanField(_('Consumed?'), default=False)
    created = models.DateTimeField(_('Creation date'), auto_now_add=True)
    consumed = models.DateTimeField(_('Consumption date'),
                                    null=True, blank=True)

    def __init__(self, *args, **kwargs):
        super(Invitation, self).__init__(*args, **kwargs)
        if not self.id:
            self.code = _generate_invitation_code()

    def consume(self):
        self.is_consumed = True
        self.consumed = datetime.now()
        self.save()

    def __unicode__(self):
        return '%s -> %s [%d]' % (self.inviter, self.username, self.code)


class EmailChangeManager(models.Manager):

    @transaction.commit_on_success
    def change_email(self, activation_key):
        """
        Validate an activation key and change the corresponding
        ``User`` if valid.

        If the key is valid and has not expired, return the ``User``
        after activating.

        If the key is not valid or has expired, return ``None``.

        If the key is valid but the ``User`` is already active,
        return ``None``.

        After successful email change the activation record is deleted.

        Throws ValueError if there is already
        """
        try:
            email_change = self.model.objects.get(
                activation_key=activation_key)
            if email_change.activation_key_expired():
                email_change.delete()
                raise EmailChange.DoesNotExist
            # is there an active user with this address?
            try:
                AstakosUser.objects.get(
                    email__iexact=email_change.new_email_address)
            except AstakosUser.DoesNotExist:
                pass
            else:
                raise ValueError(_('The new email address is reserved.'))
            # update user
            user = AstakosUser.objects.select_for_update().\
                get(pk=email_change.user_id)
            old_email = user.email
            user.set_email(email_change.new_email_address)
            user.save()
            email_change.delete()
            msg = "User %s changed email from %s to %s"
            logger.log(astakos_settings.LOGGING_LEVEL, msg, user.log_display,
                       old_email, user.email)
            return user
        except EmailChange.DoesNotExist:
            raise ValueError(_('Invalid activation key.'))


class EmailChange(models.Model):
    new_email_address = models.EmailField(
        _(u'new e-mail address'),
        help_text=_('Provide a new email address. Until you verify the new '
                    'address by following the activation link that will be '
                    'sent to it, your old email address will remain active.'))
    user = models.ForeignKey(
        AstakosUser, unique=True, related_name='emailchanges')
    requested_at = models.DateTimeField(auto_now_add=True)
    activation_key = models.CharField(
        max_length=40, unique=True, db_index=True)

    objects = EmailChangeManager()

    def get_url(self):
        return reverse('email_change_confirm',
                       urlconf="synnefo.webproject.urls",
                       kwargs={'activation_key': self.activation_key})

    def activation_key_expired(self):
        expiration_date = timedelta(
            days=astakos_settings.EMAILCHANGE_ACTIVATION_DAYS)
        return self.requested_at + expiration_date < datetime.now()


class AdditionalMail(models.Model):
    """
    Model for registring invitations
    """
    owner = models.ForeignKey(AstakosUser)
    email = models.EmailField()


def _generate_invitation_code():
    while True:
        code = randint(1, 2L ** 63 - 1)
        try:
            Invitation.objects.get(code=code)
            # An invitation with this code already exists, try again
        except Invitation.DoesNotExist:
            return code


def get_latest_terms():
    try:
        term = ApprovalTerms.objects.order_by('-id')[0]
        return term
    except IndexError:
        pass
    return None


class PendingThirdPartyUser(models.Model):
    """
    Model for registring successful third party user authentications
    """
    third_party_identifier = models.CharField(
        _('Third-party identifier'), max_length=255, null=True, blank=True)
    provider = models.CharField(_('Provider'), max_length=255, blank=True)
    email = models.EmailField(_('e-mail address'), blank=True, null=True)
    first_name = models.CharField(_('first name'), max_length=30, blank=True,
                                  null=True)
    last_name = models.CharField(_('last name'), max_length=30, blank=True,
                                 null=True)
    affiliation = models.CharField('Affiliation', max_length=255, blank=True,
                                   null=True)
    username = models.CharField(
        _('username'), max_length=30, unique=True,
        help_text=_("Required. 30 characters or fewer. "
                    "Letters, numbers and @/./+/-/_ characters"))
    token = models.CharField(_('Token'), max_length=255, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    info = models.TextField(default="", null=True, blank=True)

    class Meta:
        unique_together = ("provider", "third_party_identifier")

    def get_user_instance(self):
        """
        Create a new AstakosUser instance based on details provided when user
        initially signed up.
        """
        d = copy.copy(self.__dict__)
        d.pop('_state', None)
        d.pop('id', None)
        d.pop('token', None)
        d.pop('created', None)
        d.pop('info', None)
        d.pop('affiliation', None)
        d.pop('provider', None)
        d.pop('third_party_identifier', None)
        user = AstakosUser(**d)

        return user

    @property
    def realname(self):
        return '%s %s' % (self.first_name, self.last_name)

    @realname.setter
    def realname(self, value):
        first, last = split_realname(value)
        self.first_name = first
        self.last_name = last

    def save(self, *args, **kwargs):
        if not self.id:
            # set username
            while not self.username:
                username = uuid.uuid4().hex[:30]
                try:
                    AstakosUser.objects.get(username=username)
                except AstakosUser.DoesNotExist:
                    self.username = username
        super(PendingThirdPartyUser, self).save(*args, **kwargs)

    def generate_token(self):
        self.password = self.third_party_identifier
        self.last_login = datetime.now()
        self.token = default_token_generator.make_token(self)

    def existing_user(self):
        return AstakosUser.objects.filter(
            auth_providers__module=self.provider,
            auth_providers__identifier=self.third_party_identifier)

    def get_provider(self, user):
        params = {
            'info_data': self.info,
            'affiliation': self.affiliation
        }
        return auth.get_provider(self.provider, user,
                                 self.third_party_identifier, **params)


class SessionCatalog(models.Model):
    session_key = models.CharField(_('session key'), max_length=40)
    user = models.ForeignKey(AstakosUser, related_name='sessions', null=True)


class UserSetting(models.Model):
    user = models.ForeignKey(AstakosUser)
    setting = models.CharField(max_length=255)
    value = models.IntegerField()

    class Meta:
        unique_together = ("user", "setting")


### PROJECTS ###
################

class Chain(models.Model):
    chain = models.AutoField(primary_key=True)

    def __unicode__(self):
        return "%s" % (self.chain,)


def new_chain():
    c = Chain.objects.create()
    return c


class ProjectApplicationManager(models.Manager):

    def pending_per_project(self, projects):
        apps = self.filter(state=self.model.PENDING,
                           chain__in=projects).order_by('chain', '-id')
        checked_chain = None
        projs = {}
        for app in apps:
            chain = app.chain_id
            if chain != checked_chain:
                checked_chain = chain
                projs[chain] = app
        return projs


class ProjectApplication(models.Model):
    applicant = models.ForeignKey(
        AstakosUser,
        related_name='projects_applied',
        db_index=True)

    PENDING = 0
    APPROVED = 1
    REPLACED = 2
    DENIED = 3
    DISMISSED = 4
    CANCELLED = 5

    MAX_HOMEPAGE_LENGTH = 255
    MAX_NAME_LENGTH = 80

    state = models.IntegerField(default=PENDING,
                                db_index=True)
    owner = models.ForeignKey(
        AstakosUser,
        related_name='projects_owned',
        null=True,
        db_index=True)
    chain = models.ForeignKey('Project',
                              related_name='chained_apps',
                              db_column='chain')
    name = models.CharField(max_length=MAX_NAME_LENGTH, null=True)
    homepage = models.URLField(max_length=MAX_HOMEPAGE_LENGTH, null=True,
                               verify_exists=False)
    description = models.TextField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True)
    member_join_policy = models.IntegerField(null=True)
    member_leave_policy = models.IntegerField(null=True)
    limit_on_members_number = models.BigIntegerField(null=True)
    resource_grants = models.ManyToManyField(
        Resource,
        null=True,
        blank=True,
        through='ProjectResourceGrant')
    comments = models.TextField(null=True, blank=True)
    issue_date = models.DateTimeField(auto_now_add=True)
    response_date = models.DateTimeField(null=True, blank=True)
    response = models.TextField(null=True, blank=True)
    response_actor = models.ForeignKey(AstakosUser, null=True,
                                       related_name='responded_apps')
    waive_date = models.DateTimeField(null=True, blank=True)
    waive_reason = models.TextField(null=True, blank=True)
    waive_actor = models.ForeignKey(AstakosUser, null=True,
                                    related_name='waived_apps')
    private = models.NullBooleanField(default=False)

    objects = ProjectApplicationManager()

    # Compiled queries
    Q_PENDING = Q(state=PENDING)
    Q_APPROVED = Q(state=APPROVED)
    Q_DENIED = Q(state=DENIED)

    class Meta:
        unique_together = ("chain", "id")

    def __unicode__(self):
        return "%s applied by %s" % (self.name, self.applicant)

    # TODO: Move to a more suitable place
    APPLICATION_STATE_DISPLAY = {
        PENDING:   _('Pending review'),
        APPROVED:  _('Approved'),
        REPLACED:  _('Replaced'),
        DENIED:    _('Denied'),
        DISMISSED: _('Dismissed'),
        CANCELLED: _('Cancelled')
    }

    @property
    def log_display(self):
        return "application %s (%s) for project %s" % (
            self.id, self.name, self.chain)

    def state_display(self):
        return self.APPLICATION_STATE_DISPLAY.get(self.state, _('Unknown'))

    @property
    def resource_set(self):
        return self.projectresourcegrant_set.order_by('resource__name')

    @property
    def resource_policies(self):
        return [unicode(rp) for rp in self.projectresourcegrant_set.all()]

    def is_modification(self):
        return self.chain.is_initialized()

    def chained_applications(self):
        return ProjectApplication.objects.filter(chain=self.chain)

    def denied_modifications(self):
        q = self.chained_applications()
        q = q.filter(Q(state=self.DENIED))
        q = q.filter(~Q(id=self.id))
        return q

    def last_denied(self):
        try:
            return self.denied_modifications().order_by('-id')[0]
        except IndexError:
            return None

    def has_denied_modifications(self):
        return bool(self.last_denied())

    def can_cancel(self):
        return self.state == self.PENDING

    def cancel(self, actor=None, reason=None):
        if not self.can_cancel():
            m = _("cannot cancel: application '%s' in state '%s'") % (
                self.id, self.state)
            raise AssertionError(m)

        self.state = self.CANCELLED
        self.waive_date = datetime.now()
        self.waive_reason = reason
        self.waive_actor = actor
        self.save()

    def can_dismiss(self):
        return self.state == self.DENIED

    def dismiss(self, actor=None, reason=None):
        if not self.can_dismiss():
            m = _("cannot dismiss: application '%s' in state '%s'") % (
                self.id, self.state)
            raise AssertionError(m)

        self.state = self.DISMISSED
        self.waive_date = datetime.now()
        self.waive_reason = reason
        self.waive_actor = actor
        self.save()

    def can_deny(self):
        return self.state == self.PENDING

    def deny(self, actor=None, reason=None):
        if not self.can_deny():
            m = _("cannot deny: application '%s' in state '%s'") % (
                self.id, self.state)
            raise AssertionError(m)

        self.state = self.DENIED
        self.response_date = datetime.now()
        self.response = reason
        self.response_actor = actor
        self.save()

    def can_approve(self):
        return self.state == self.PENDING

    def approve(self, actor=None, reason=None):
        if not self.can_approve():
            m = _("cannot approve: project '%s' in state '%s'") % (
                self.name, self.state)
            raise AssertionError(m)  # invalid argument

        now = datetime.now()
        self.state = self.APPROVED
        self.response_date = now
        self.response = reason
        self.response_actor = actor
        self.save()

    @property
    def member_join_policy_display(self):
        policy = self.member_join_policy
        return presentation.PROJECT_MEMBER_JOIN_POLICIES.get(policy)

    @property
    def member_leave_policy_display(self):
        policy = self.member_leave_policy
        return presentation.PROJECT_MEMBER_LEAVE_POLICIES.get(policy)


class ProjectResourceGrantManager(models.Manager):
    def grants_per_app(self, applications):
        app_ids = [app.id for app in applications]
        grants = self.filter(
            project_application__in=app_ids).select_related("resource")
        return _partition_by(lambda g: g.project_application_id, grants)


class ProjectResourceGrant(models.Model):

    resource = models.ForeignKey(Resource)
    project_application = models.ForeignKey(ProjectApplication)
    project_capacity = models.BigIntegerField()
    member_capacity = models.BigIntegerField()

    objects = ProjectResourceGrantManager()

    class Meta:
        unique_together = ("resource", "project_application")

    def display_member_capacity(self):
        return units.show(self.member_capacity, self.resource.unit,
                          inf="Unlimited")

    def display_project_capacity(self):
        return units.show(self.project_capacity, self.resource.unit,
                          inf="Unlimited")

    def project_diffs(self):
        project = self.project_application.chain
        try:
            project_resource = project.resource_set.get(resource=self.resource)
        except ProjectResourceQuota.DoesNotExist:
            return [self.project_capacity, self.member_capacity]

        project_diff = \
            self.project_capacity - project_resource.project_capacity
        if self.project_capacity == units.PRACTICALLY_INFINITE:
            project_diff = units.PRACTICALLY_INFINITE
        if project_resource.project_capacity == units.PRACTICALLY_INFINITE:
            project_diff = -units.PRACTICALLY_INFINITE

        member_diff = self.member_capacity - project_resource.member_capacity
        if self.member_capacity == units.PRACTICALLY_INFINITE:
            member_diff = units.PRACTICALLY_INFINITE
        if project_resource.member_capacity == units.PRACTICALLY_INFINITE:
            member_diff = -units.PRACTICALLY_INFINITE

        return [project_diff, member_diff]

    def display_project_diff(self):
        proj, member = self.project_diffs()
        proj_abs, member_abs = proj, member
        unit = self.resource.unit

        def disp(v, disp_func=None):
            if not disp_func:
                disp_func = lambda : ''

            if v == 0:
                return ''
            sign = u'+' if v >= 0 else u'-'
            ext = units.show(abs(v), unit, inf="Unlimited")
            if ext == "Unlimited" and sign == u'+':
                disp = disp_func()
                if disp:
                    ext = "from %s" % disp
            else:
                disp = disp_func()
                ext = sign + "" + ext
            return unicode(ext)

        project_resource = None
        try:
            project = self.project_application.chain
            project_resource = project.resource_set.get(resource=self.resource)
        except:
            pass

        memb_disp = project_resource.display_member_capacity if \
            project_resource else None
        proj_disp = project_resource.display_project_capacity if \
            project_resource else None
        return [disp(proj_abs, proj_disp),
                disp(member_abs, memb_disp)]

    def __unicode__(self):
        return 'Max %s per member: %s; project total: %s' % (
            self.resource.pluralized_display_name,
            self.display_member_capacity(),
            self.display_project_capacity())


class ProjectManager(models.Manager):
    def expired_projects(self):
        model = self.model
        q = (Q(state__in=[model.NORMAL, model.SUSPENDED]) &
             Q(end_date__lt=datetime.now()))
        return self.filter(q)

    def user_accessible_projects(self, user):
        """
        Return projects accessible by specified user.
        """
        model = self.model
        if user.is_project_admin():
            flt = Q()
        else:
            membs = user.projectmembership_set.associated()
            memb_projects = membs.values_list("project", flat=True)
            flt = (Q(owner=user) |
                   Q(last_application__applicant=user) |
                   Q(id__in=memb_projects))

        relevant = ~Q(state=model.DELETED)
        return self.filter(flt, relevant).order_by(
            'creation_date').select_related('last_application', 'owner')

    def search_by_name(self, *search_strings):
        q = Q()
        for s in search_strings:
            q = q | Q(name__icontains=s)
        return self.filter(q)

    def initialized(self, flt=None):
        q = Q(state__in=self.model.INITIALIZED_STATES)
        if flt is not None:
            q &= flt
        return self.filter(q)

    @property
    def has_infinite_members_limit(self):
        return self.limit_on_members_number == units.PRACTICALLY_INFINITE



class Project(models.Model):

    id = models.BigIntegerField(db_column='id', primary_key=True)

    last_application = models.ForeignKey(ProjectApplication, null=True,
                                         related_name='last_of_project')

    members = models.ManyToManyField(
        AstakosUser,
        through='ProjectMembership')

    creation_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(
        max_length=ProjectApplication.MAX_NAME_LENGTH,
        null=True,
        db_index=True,
        unique=True)

    UNINITIALIZED = 0
    NORMAL = 1
    SUSPENDED = 10
    TERMINATED = 100
    DELETED = 1000

    INITIALIZED_STATES = [NORMAL,
                          SUSPENDED,
                          TERMINATED,
                          ]

    ALIVE_STATES = [NORMAL,
                    SUSPENDED,
                    ]

    SKIP_STATES = [DELETED,
                   TERMINATED,
                   ]

    HIDDEN_STATES = [DELETED]

    DEACTIVATED_STATES = [SUSPENDED, TERMINATED]

    state = models.IntegerField(default=UNINITIALIZED,
                                db_index=True)
    uuid = models.CharField(max_length=255, unique=True)

    owner = models.ForeignKey(
        AstakosUser,
        related_name='projs_owned',
        null=True,
        db_index=True)
    realname = models.CharField(max_length=ProjectApplication.MAX_NAME_LENGTH)
    homepage = models.URLField(
        max_length=ProjectApplication.MAX_HOMEPAGE_LENGTH,
        verify_exists=False)
    description = models.TextField(blank=True)
    end_date = models.DateTimeField()
    member_join_policy = models.IntegerField()
    member_leave_policy = models.IntegerField()
    limit_on_members_number = models.BigIntegerField()
    resource_grants = models.ManyToManyField(
        Resource,
        null=True,
        blank=True,
        through='ProjectResourceQuota')
    private = models.BooleanField(default=False)
    is_base = models.BooleanField(default=False)

    objects = ProjectManager()

    def __unicode__(self):
        return _("<project %s '%s'>") % (self.id, self.realname)

    O_UNINITIALIZED = -1
    O_PENDING = 0
    O_ACTIVE = 1
    O_ACTIVE_PENDING = 2
    O_DENIED = 3
    O_DISMISSED = 4
    O_CANCELLED = 5
    O_SUSPENDED = 10
    O_TERMINATED = 100
    O_DELETED = 1000

    O_STATE_DISPLAY = {
        O_UNINITIALIZED: _("Uninitialized"),
        O_PENDING:    _("Pending"),
        O_ACTIVE:     _("Active"),
        O_DENIED:     _("Denied"),
        O_DISMISSED:  _("Dismissed"),
        O_CANCELLED:  _("Cancelled"),
        O_SUSPENDED:  _("Suspended"),
        O_TERMINATED: _("Terminated"),
        O_DELETED:    _("Deleted"),
    }

    O_STATE_UNINITIALIZED = {
        None: O_UNINITIALIZED,
        ProjectApplication.PENDING: O_PENDING,
        ProjectApplication.DENIED:  O_DENIED,
        }
    O_STATE_DELETED = {
        None: O_DELETED,
        ProjectApplication.DISMISSED: O_DISMISSED,
        ProjectApplication.CANCELLED: O_CANCELLED,
        }

    OVERALL_STATE = {
        NORMAL: lambda app_state: Project.O_ACTIVE,
        UNINITIALIZED: lambda app_state: Project.O_STATE_UNINITIALIZED.get(
            app_state, None),
        DELETED: lambda app_state: Project.O_STATE_DELETED.get(
            app_state, None),
        SUSPENDED: lambda app_state: Project.O_SUSPENDED,
        TERMINATED: lambda app_state: Project.O_TERMINATED,
        }

    def display_name_for_user(self, user):
        if not self.is_base:
            return self.realname

        if user.uuid == self.realname.replace("system:", ""):
            return "System project"

        if user.is_project_admin():
            return "[system] %s" % (self.display_name(email=True), )

        return self.display_name

    def display_name(self, email=False):
        if self.is_base:
            uuid = self.realname.replace("system:", "")
            try:
                user = AstakosUser.objects.get(uuid=uuid)
                if email:
                    username = "%s %s" % (user.email, user.realname)
                else:
                    username = user.realname
            except AstakosUser.DoesNotExist:
                username = uuid

            return username
        return self.realname

    @classmethod
    def _overall_state(cls, project_state, app_state):
        os = cls.OVERALL_STATE.get(project_state, None)
        if os is None:
            return None
        return os(app_state)

    def overall_state(self):
        app_state = (self.last_application.state
                     if self.last_application else None)
        return self._overall_state(self.state, app_state)

    def last_pending_application(self):
        app = self.last_application
        if app and app.state == ProjectApplication.PENDING:
            return app
        return None

    def last_pending_modification(self):
        last_pending = self.last_pending_application()
        if self.state != Project.UNINITIALIZED:
            return last_pending
        return None

    def state_display(self):
        return self.O_STATE_DISPLAY.get(self.overall_state(), _('Unknown'))

    def expiration_info(self):
        return (unicode(self.id), self.name, self.state_display(),
                unicode(self.end_date))

    def last_deactivation(self):
        objs = self.log.filter(to_state__in=self.DEACTIVATED_STATES)
        ls = objs.order_by("-date")
        if not ls:
            return None
        return ls[0]

    def is_deactivated(self, reason=None):
        if reason is not None:
            return self.state == reason

        return self.state != self.NORMAL

    def is_active(self):
        return self.state == self.NORMAL

    def is_initialized(self):
        return self.state in self.INITIALIZED_STATES

    ### Deactivation calls

    def _log_create(self, from_state, to_state, actor=None, reason=None,
                    comments=None):
        now = datetime.now()
        self.log.create(from_state=from_state, to_state=to_state, date=now,
                        actor=actor, reason=reason, comments=comments)

    def set_state(self, to_state, actor=None, reason=None, comments=None):
        self._log_create(self.state, to_state, actor=actor, reason=reason,
                         comments=comments)
        self.state = to_state
        self.save()

    def terminate(self, actor=None, reason=None):
        self.set_state(self.TERMINATED, actor=actor, reason=reason)
        self.name = None
        self.save()

    def suspend(self, actor=None, reason=None):
        self.set_state(self.SUSPENDED, actor=actor, reason=reason)

    def resume(self, actor=None, reason=None):
        self.set_state(self.NORMAL, actor=actor, reason=reason)
        if self.name is None:
            self.name = self.realname
            self.save()

    def activate(self, actor=None, reason=None):
        assert self.state != self.DELETED, \
            "cannot activate: %s is deleted" % self
        if self.state != self.NORMAL:
            self.set_state(self.NORMAL, actor=actor, reason=reason)
        if self.name != self.realname:
            self.name = self.realname
            self.save()

    def set_deleted(self, actor=None, reason=None):
        self.set_state(self.DELETED, actor=actor, reason=reason)

    def can_modify(self):
        return self.state not in [self.UNINITIALIZED, self.DELETED]

    ### Logical checks
    @property
    def is_alive(self):
        return self.state in [self.NORMAL, self.SUSPENDED]

    @property
    def is_terminated(self):
        return self.is_deactivated(self.TERMINATED)

    @property
    def is_suspended(self):
        return self.is_deactivated(self.SUSPENDED)

    def violates_members_limit(self, adding=0):
        limit = self.limit_on_members_number
        return (len(self.approved_members) + adding > limit)

    ### Other

    def count_pending_memberships(self):
        return self.projectmembership_set.requested().count()

    def members_count(self):
        return self.approved_memberships.count()

    @property
    def approved_memberships(self):
        query = ProjectMembership.Q_ACCEPTED_STATES
        return self.projectmembership_set.filter(query)

    @property
    def approved_members(self):
        return [m.person for m in self.approved_memberships]

    @property
    def member_join_policy_display(self):
        policy = self.member_join_policy
        return presentation.PROJECT_MEMBER_JOIN_POLICIES.get(policy)

    @property
    def member_leave_policy_display(self):
        policy = self.member_leave_policy
        return presentation.PROJECT_MEMBER_LEAVE_POLICIES.get(policy)

    @property
    def has_infinite_members_limit(self):
        return self.limit_on_members_number == units.PRACTICALLY_INFINITE

    @property
    def resource_set(self):
        return self.projectresourcequota_set.order_by('resource__name')


def create_project(**kwargs):
    if "uuid" not in kwargs:
        kwargs["uuid"] = str(uuid.uuid4())
    return Project.objects.create(**kwargs)


class ProjectResourceQuotaManager(models.Manager):
    def quotas_per_project(self, projects):
        proj_ids = [proj.id for proj in projects]
        quotas = self.filter(
            project__in=proj_ids).select_related("resource")
        return _partition_by(lambda g: g.project_id, quotas)


class ProjectResourceQuota(models.Model):

    resource = models.ForeignKey(Resource)
    project = models.ForeignKey(Project)
    project_capacity = models.BigIntegerField(default=0)
    member_capacity = models.BigIntegerField(default=0)

    objects = ProjectResourceQuotaManager()

    class Meta:
        unique_together = ("resource", "project")

    def display_member_capacity(self):
        return units.show(self.member_capacity, self.resource.unit,
                          inf="Unlimited")

    def display_project_capacity(self):
        return units.show(self.project_capacity, self.resource.unit,
                          inf="Unlimited")


class ProjectLogManager(models.Manager):
    def last_deactivations(self, projects):
        logs = self.filter(
            project__in=projects,
            to_state__in=Project.DEACTIVATED_STATES).order_by("-date")
        return first_of_group(lambda l: l.project_id, logs)


class ProjectLog(models.Model):
    project = models.ForeignKey(Project, related_name="log")
    from_state = models.IntegerField(null=True)
    to_state = models.IntegerField()
    date = models.DateTimeField()
    actor = models.ForeignKey(AstakosUser, null=True)
    reason = models.TextField(null=True)
    comments = models.TextField(null=True)

    objects = ProjectLogManager()


class ProjectLock(models.Model):
    pass


class ProjectMembershipManager(models.Manager):

    def any_accepted(self):
        q = self.model.Q_ACCEPTED_STATES
        return self.filter(q)

    def actually_accepted(self, projects=None):
        q = self.model.Q_ACTUALLY_ACCEPTED
        if projects is not None:
            q &= Q(project__in=projects)
        return self.filter(q)

    def actually_accepted_and_active(self):
        q = self.model.Q_ACTUALLY_ACCEPTED
        q &= Q(project__state=Project.NORMAL)
        return self.filter(q)

    def initialized(self, projects=None):
        q = Q(initialized=True)
        if projects is not None:
            q &= Q(project__in=projects)
        return self.filter(q)

    def requested(self):
        return self.filter(state=ProjectMembership.REQUESTED)

    def suspended(self):
        return self.filter(state=ProjectMembership.USER_SUSPENDED)

    def associated(self):
        return self.filter(state__in=ProjectMembership.ASSOCIATED_STATES)

    def any_accepted_per_project(self, projects):
        ms = self.any_accepted().filter(project__in=projects)
        return _partition_by(lambda m: m.project_id, ms)

    def requested_per_project(self, projects):
        ms = self.requested().filter(project__in=projects)
        return _partition_by(lambda m: m.project_id, ms)

    def one_per_project(self):
        ms = self.all().select_related(
            'project', 'project__application',
            'project__application__owner', 'project_application__applicant',
            'person')
        m_per_p = {}
        for m in ms:
            m_per_p[m.project_id] = m
        return m_per_p


class ProjectMembership(models.Model):

    person = models.ForeignKey(AstakosUser)
    project = models.ForeignKey(Project)

    REQUESTED = 0
    ACCEPTED = 1
    LEAVE_REQUESTED = 5
    # User deactivation
    USER_SUSPENDED = 10
    REJECTED = 100
    CANCELLED = 101
    REMOVED = 200

    ASSOCIATED_STATES = set([REQUESTED,
                             ACCEPTED,
                             LEAVE_REQUESTED,
                             USER_SUSPENDED,
                             ])

    ACCEPTED_STATES = set([ACCEPTED,
                           LEAVE_REQUESTED,
                           USER_SUSPENDED,
                           ])

    ACTUALLY_ACCEPTED = set([ACCEPTED, LEAVE_REQUESTED])

    state = models.IntegerField(default=REQUESTED,
                                db_index=True)

    initialized = models.BooleanField(default=False)
    objects = ProjectMembershipManager()

    # Compiled queries
    Q_ACCEPTED_STATES = Q(state__in=ACCEPTED_STATES)
    Q_ACTUALLY_ACCEPTED = Q(state=ACCEPTED) | Q(state=LEAVE_REQUESTED)

    MEMBERSHIP_STATE_DISPLAY = {
        REQUESTED:       _('Requested'),
        ACCEPTED:        _('Accepted'),
        LEAVE_REQUESTED: _('Leave Requested'),
        USER_SUSPENDED:  _('Suspended'),
        REJECTED:        _('Rejected'),
        CANCELLED:       _('Cancelled'),
        REMOVED:         _('Removed'),
    }

    USER_FRIENDLY_STATE_DISPLAY = {
        REQUESTED:       _('Join requested'),
        ACCEPTED:        _('Accepted member'),
        LEAVE_REQUESTED: _('Requested to leave'),
        USER_SUSPENDED:  _('Suspended member'),
        REJECTED:        _('Join request rejected'),
        CANCELLED:       _('Join request cancelled'),
        REMOVED:         _('Removed member'),
    }

    def state_display(self):
        return self.MEMBERSHIP_STATE_DISPLAY.get(self.state, _('Unknown'))

    def user_friendly_state_display(self):
        return self.USER_FRIENDLY_STATE_DISPLAY.get(self.state, _('Unknown'))

    class Meta:
        unique_together = ("person", "project")
        #index_together = [["project", "state"]]

    def __unicode__(self):
        return (_("<'%s' membership in '%s'>") %
                (self.person.username, self.project))

    def latest_log(self):
        logs = self.log.all()
        logs_d = _partition_by(lambda l: l.to_state, logs)
        for s, s_logs in logs_d.iteritems():
            logs_d[s] = max(s_logs, key=(lambda l: l.date))
        return logs_d

    def _log_create(self, from_state, to_state, actor=None, reason=None,
                    comments=None):
        now = datetime.now()
        self.log.create(from_state=from_state, to_state=to_state, date=now,
                        actor=actor, reason=reason, comments=comments)

    def set_state(self, to_state, actor=None, reason=None, comments=None):
        self._log_create(self.state, to_state, actor=actor, reason=reason,
                         comments=comments)
        self.state = to_state
        self.save()

    def is_active(self):
        return (self.project.state == Project.NORMAL and
                self.state in self.ACTUALLY_ACCEPTED)

    ACTION_CHECKS = {
        "join": lambda m: m.state not in m.ASSOCIATED_STATES,
        "accept": lambda m: m.state == m.REQUESTED,
        "enroll": lambda m: m.state not in m.ACCEPTED_STATES,
        "leave": lambda m: m.state in m.ACCEPTED_STATES,
        "leave_request": lambda m: m.state in m.ACCEPTED_STATES,
        "deny_leave": lambda m: m.state == m.LEAVE_REQUESTED,
        "cancel_leave": lambda m: m.state == m.LEAVE_REQUESTED,
        "remove": lambda m: m.state in m.ACCEPTED_STATES,
        "reject": lambda m: m.state == m.REQUESTED,
        "cancel": lambda m: m.state == m.REQUESTED,
    }

    ACTION_STATES = {
        "join":          REQUESTED,
        "accept":        ACCEPTED,
        "enroll":        ACCEPTED,
        "leave_request": LEAVE_REQUESTED,
        "deny_leave":    ACCEPTED,
        "cancel_leave":  ACCEPTED,
        "remove":        REMOVED,
        "reject":        REJECTED,
        "cancel":        CANCELLED,
    }

    def check_action(self, action):
        try:
            check = self.ACTION_CHECKS[action]
        except KeyError:
            raise ValueError("No check found for action '%s'" % action)
        return check(self)

    def perform_action(self, action, actor=None, reason=None):
        if not self.check_action(action):
            m = _("%s: attempted action '%s' in state '%s'") % (
                self, action, self.state)
            raise AssertionError(m)
        try:
            s = self.ACTION_STATES[action]
        except KeyError:
            raise ValueError("No such action '%s'" % action)
        if s == self.ACCEPTED:
            self.initialized = True
        return self.set_state(s, actor=actor, reason=reason)


class ProjectMembershipLogManager(models.Manager):
    def last_logs(self, memberships):
        logs = self.filter(membership__in=memberships).order_by("-date")
        logs = _partition_by(lambda l: l.membership_id, logs)

        for memb_id, m_logs in logs.iteritems():
            logs[memb_id] = first_of_group(lambda l: l.to_state, m_logs)
        return logs


class ProjectMembershipLog(models.Model):
    membership = models.ForeignKey(ProjectMembership, related_name="log")
    from_state = models.IntegerField(null=True)
    to_state = models.IntegerField()
    date = models.DateTimeField()
    actor = models.ForeignKey(AstakosUser, null=True)
    reason = models.TextField(null=True)
    comments = models.TextField(null=True)

    objects = ProjectMembershipLogManager()


### SIGNALS ###
################

def resource_post_save(sender, instance, created, **kwargs):
    pass

post_save.connect(resource_post_save, sender=Resource)


def renew_token(sender, instance, **kwargs):
    if not instance.auth_token:
        instance.renew_token()
pre_save.connect(renew_token, sender=Component)
