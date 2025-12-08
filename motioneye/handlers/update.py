# Copyright (c) 2020 Vlsarro
# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
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

import logging

from motioneye.handlers.base import BaseHandler
from motioneye.update import get_update_status, list_remote_branches, perform_update

__all__ = ('UpdateHandler',)


class UpdateHandler(BaseHandler):
    @BaseHandler.auth(admin=True)
    def get(self):
        logging.debug('listing versions')

        list_branches = self.get_argument('list_branches', '0').lower() in ('1', 'true', 'yes')
        repo_url = self.get_argument('repo_url', None)
        branch = self.get_argument('branch', None)

        if list_branches:
            self.finish_json({'branches': list_remote_branches(repo_url=repo_url)})
            return

        status = get_update_status(repo_url=repo_url, branch=branch)

        self.finish_json(status)

    @BaseHandler.auth(admin=True)
    def post(self):
        version = self.get_argument('version')
        repo_url = self.get_argument('repo_url', None)
        branch = self.get_argument('branch', None)

        logging.debug(f'performing update to version {version} (branch={branch}, repo={repo_url})')

        result = perform_update(version, repo_url=repo_url, branch=branch)

        self.finish_json(result)
