# -*- encoding: utf-8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see <https://www.gnu.org/licenses/>.
import datetime
import re
import string

import qubes.ext

_version_re = re.compile(r"[0-9]{1,3}\.[0-9]{1,3}")

class CoreFeatures(qubes.ext.Extension):
    # pylint: disable=too-few-public-methods
    @qubes.ext.handler('features-request')
    async def qubes_features_request(self, vm, event, untrusted_features):
        '''Handle features provided by qubes-core-agent and qubes-gui-agent'''
        # pylint: disable=unused-argument
        if getattr(vm, 'template', None):
            vm.log.warning(
                'Ignoring qubes.NotifyTools for template-based VM')
            return

        if "os-distribution" in untrusted_features \
                and untrusted_features["os-distribution"]:
            # entry point already validates values for safe characters
            vm.features["os-distribution"] = \
                untrusted_features["os-distribution"]
        if "os-version" in untrusted_features \
                and untrusted_features["os-version"]:
            # no letters in versions please
            safe_set = string.digits + ".-"
            untrusted_version = untrusted_features["os-version"]
            if all(c in safe_set for c in untrusted_version) \
                    and untrusted_version[0].isdigit():
                vm.features["os-version"] = untrusted_version
            else:
                # safe to log the value as passed preliminary filtering already
                vm.log.warning(
                    "Invalid 'os-version' value '%s', must start "
                    "with a digit and only digits and _ or . are allowed",
                    untrusted_version)
        if "os-eol" in untrusted_features \
                and untrusted_features["os-eol"]:
            untrusted_eol = untrusted_features["os-eol"]
            valid = False
            if re.match(r"\A\d{4}-\d{2}-\d{2}\Z", untrusted_eol):
                try:
                    datetime.date.fromisoformat(untrusted_eol)
                    valid = True
                except ValueError:
                    pass
            if valid:
                vm.features["os-eol"] = untrusted_eol
            else:
                vm.log.warning(
                    "Invalid 'os-eol' value '%s', expected YYYY-MM-DD",
                    untrusted_eol)

        requested_features = {}
        for feature in (
                'qrexec', 'gui', 'gui-emulated', 'qubes-firewall', 'vmexec'):
            untrusted_value = untrusted_features.get(feature, None)
            if untrusted_value in ('1', '0'):
                requested_features[feature] = bool(int(untrusted_value))

        if 'qubes-agent-version' in untrusted_features:
            untrusted_value = untrusted_features['qubes-agent-version']
            if _version_re.fullmatch(untrusted_value):
                vm.features['qubes-agent-version'] = untrusted_value
        del untrusted_features

        # default user for qvm-run etc
        # starting with Qubes 4.x ignored
        # qrexec agent presence (0 or 1)
        # gui agent presence (0 or 1)

        qrexec_before = vm.features.get('qrexec', False)
        for feature in ('qrexec', 'gui', 'gui-emulated'):
            # do not allow (Template)VM to override setting if already set
            # some other way
            if feature in requested_features and feature not in vm.features:
                vm.features[feature] = requested_features[feature]

        # those features can be freely enabled or disabled by template
        for feature in ('qubes-firewall', 'vmexec'):
            if feature in requested_features:
                vm.features[feature] = requested_features[feature]

        if not qrexec_before and vm.features.get('qrexec', False):
            # if this is the first time qrexec was advertised, now can finish
            #  template setup
            await vm.fire_event_async('template-postinstall')

    def set_servicevm_feature(self, subject):
        if getattr(subject, 'provides_network', False):
            subject.features['servicevm'] = 1
            # icon is calculated based on this feature
            subject.fire_event('property-reset:icon', name='icon')
        elif 'servicevm' in subject.features:
            del subject.features['servicevm']
            # icon is calculated based on this feature
            subject.fire_event('property-reset:icon', name='icon')

    @qubes.ext.handler('property-set:provides_network')
    def on_property_set(self, subject, event, name, newvalue, oldvalue=None):
        # pylint: disable=unused-argument
        self.set_servicevm_feature(subject)

    @qubes.ext.handler('property-reset:provides_network')
    def on_property_reset(self, subject, event, name, oldvalue=None):
        # pylint: disable=unused-argument
        self.set_servicevm_feature(subject)

    @qubes.ext.handler('domain-load')
    def on_domain_load(self, subject, event):
        # pylint: disable=unused-argument
        self.set_servicevm_feature(subject)
