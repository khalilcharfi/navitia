# Copyright (c) 2001-2021, Canal TP and/or its affiliates. All rights reserved.
#
# This file is part of Navitia,
#     the software to build cool stuff with public transport.
#
# Hope you'll enjoy and contribute to this project,
#     powered by Canal TP (www.canaltp.fr).
# Help us simplify mobility and open public transport:
#     a non ending quest to the responsive locomotion way of traveling!
#
# LICENCE: This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Stay tuned using
# twitter @navitia
# channel `#navitia` on riot https://riot.im/app/#/room/#navitia:matrix.org
# https://groups.google.com/d/forum/navitia
# www.navitia.io

from __future__ import absolute_import, print_function, unicode_literals, division
from importlib import import_module
import logging
import datetime
from jormungandr import utils
from jormungandr.exceptions import ConfigException


class ExternalServiceManager(object):
    def __init__(
        self, instance, external_service_configuration, external_service_getter=None, update_interval=600
    ):
        self.logger = logging.getLogger(__name__)
        self._external_service_configuration = external_service_configuration
        self._external_service_getter = external_service_getter
        # List of external services grouped by navitia_service_type
        self._external_services_legacy = {}
        self._external_services_from_db = {}
        self._external_services_last_update = {}
        self._last_update = datetime.datetime(1970, 1, 1)
        self._update_interval = update_interval
        self.instance = instance

    def init_external_services(self):
        # Init external services from config file
        for config in self._external_service_configuration:
            # Set default arguments
            if 'args' not in config:
                config['args'] = {}
            if 'service_url' not in config['args']:
                config['args'].update({'service_url': None})
            try:
                service = utils.create_object(config)
            except KeyError as e:
                self.logger.error('Impossible to create external service with missing key: {}'.format(str(e)))
                raise KeyError('Impossible to create external service with missing key: {}'.format(str(e)))
            except Exception as e:
                self.logger.error('Impossible to create external service with wrong class: {}'.format(str(e)))
                raise ConfigException(
                    'Impossible to create external service with wrong class: {}'.format(str(e))
                )

            self._external_services_legacy.setdefault(config['navitia_service'], []).append(service)

    def _init_class(self, cls, arguments):
        """
        Create an instance of a external service according to config
        :param cls: name of the class configured in the database
        :param arguments: parameters from the database required
        :return: instance of external service
        """
        try:
            if '.' not in cls:
                self.logger.warning('impossible to build, wrongly formated class: {}'.format(cls))

            module_path, name = cls.rsplit('.', 1)
            module = import_module(module_path)
            attr = getattr(module, name)
            return attr(**arguments)
        except ImportError:
            self.logger.warning('impossible to build, cannot find class: {}'.format(cls))

    def _need_update(self, services):
        for service in services:
            if (
                service.id not in self._external_services_last_update
                or service.last_update() > self._external_services_last_update[service.id]
            ):
                return True
        return False

    def update_config(self):
        """
        Update list of external services from db
        """
        if (
            self._last_update + datetime.timedelta(seconds=self._update_interval) > datetime.datetime.utcnow()
            or not self._external_service_getter
        ):
            return

        self.logger.debug('Updating external services from db')
        self._last_update = datetime.datetime.utcnow()

        services = []
        try:
            services = self._external_service_getter()
        except Exception:
            self.logger.exception('Failure to retrieve external service configuration')
        if not services:
            self.logger.debug('No external service/All external services disabled in db')
            self._external_services_last_update = {}
            return

        if not self._need_update(services):
            return

        # We update all the services if any one of them is updated
        self._external_services_from_db = {}
        for service in services:
            self._update_external_service(service)

        # If any external service is present in database, service from configuration file in no more used.
        self._external_services_legacy = self._external_services_from_db

    def _update_external_service(self, service):
        self.logger.info('adding {} external service'.format(service.id))
        try:
            service_obj = self._init_class(service.klass, service.args)
            if service_obj not in self._external_services_from_db.get(service.navitia_service, []):
                self._external_services_from_db.setdefault(service.navitia_service, []).append(service_obj)
            self._external_services_last_update[service.id] = service.last_update()
        except Exception:
            self.logger.exception('impossible to initialize external service')

    # Here comes the function to call forseti/free_floating
    def manage_free_floatings(self, navitia_service, arguments):
        """
        Get appropriate external service for 'navitia_service' and call it
        :param navitia_service: external service to be used to query
        :param arguments: parameters to be added in the query
        :return: response: external_services json
        """
        service = self._get_external_service(navitia_service)
        return service.get_free_floatings(arguments) if service else None

    def _get_external_service(self, navitia_service):
        # Make sure we update the external services list from the database before returning them
        self.update_config()
        service = self._external_services_legacy.get(navitia_service, [])
        return service[0] if service else None

    def status(self):
        return [
            {'id': service['id'], 'timeout': service['args']['timeout'], 'fail_max': service['args']['fail_max']}
            for service in self._external_service_configuration
        ]
