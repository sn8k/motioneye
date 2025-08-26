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

# version: 2025-08-26

import logging

from motioneye.handlers.base import BaseHandler

__all__ = ('PrefsHandler',)


class PrefsHandler(BaseHandler):
    def get(self, key=None):
        if key:
            data = self.get_pref(key)
        else:
            args = self.get_all_arguments()
            data = {k: self.get_pref(k) for k in args} if args else self.get_pref(None)

        self.finish_json(data)

    def post(self, key=None):
        data = self.get_all_arguments()

        if key:
            self.set_pref(key, data.get(key))
        else:
            for pref_key, pref_value in data.items():
                self.set_pref(pref_key, pref_value)

        self.finish_json()
