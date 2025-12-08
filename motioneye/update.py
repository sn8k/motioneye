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

import datetime
import logging
import re
import shutil
import sys
from functools import cmp_to_key
from pathlib import Path

from tornado import ioloop

import motioneye
from motioneye import utils

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = REPO_ROOT / '.venv' / 'bin' / 'python'


def get_os_version():
    try:
        import platformupdate

        return platformupdate.get_os_version()

    except ImportError:
        return _get_os_version_lsb_release()


def _get_os_version_lsb_release():
    try:
        output = utils.call_subprocess('lsb_release -sri', shell=True)
        lines = output.strip().split()
        name, version = lines
        if version.lower() == 'rolling':
            version = ''

        return name, version

    except:
        return _get_os_version_uname()


def _get_os_version_uname():
    try:
        output = utils.call_subprocess('uname -rs', shell=True)
        lines = output.strip().split()
        name, version = lines

        return name, version

    except:
        return 'Linux', ''  # most likely :)


def compare_versions(version1, version2):
    version1 = re.sub('[^0-9.]', '', version1)
    version2 = re.sub('[^0-9.]', '', version2)

    def int_or_0(n):
        try:
            return int(n)

        except:
            return 0

    version1 = [int_or_0(n) for n in version1.split('.')]
    version2 = [int_or_0(n) for n in version2.split('.')]

    len1 = len(version1)
    len2 = len(version2)
    length = min(len1, len2)
    for i in range(length):
        p1 = version1[i]
        p2 = version2[i]

        if p1 < p2:
            return -1

        elif p1 > p2:
            return 1

    if len1 < len2:
        return -1

    elif len1 > len2:
        return 1

    else:
        return 0


def _is_git_repo():
    return (REPO_ROOT / '.git').is_dir()


def _get_remote_url():
    if not _is_git_repo():
        return None

    try:
        return _git('config', '--get', 'remote.origin.url')

    except Exception as exc:
        logging.warning('failed to read origin url: %s', exc)
        return None


def _git(*args):
    return utils.call_subprocess(['git', '-C', str(REPO_ROOT), *args])


def _restart_service_if_exists():
    service_name = 'motioneye.service'

    if shutil.which('systemctl'):
        try:
            unit_exists = any(
                path.exists()
                for path in (
                    Path('/etc/systemd/system') / service_name,
                    Path('/lib/systemd/system') / service_name,
                )
            )

            if unit_exists or utils.call_subprocess(
                ['systemctl', 'status', service_name]
            ):
                utils.call_subprocess(['systemctl', 'daemon-reload'])
                utils.call_subprocess(['systemctl', 'enable', '--now', service_name])
                utils.call_subprocess(['systemctl', 'restart', service_name])
                return
        except Exception as exc:
            logging.warning('systemd restart failed or service missing: %s', exc)

    if shutil.which('service'):
        try:
            if utils.call_subprocess(['service', 'motioneye', 'status']):
                utils.call_subprocess(['service', 'motioneye', 'restart'])
                return
        except Exception as exc:
            logging.warning('service restart failed or service missing: %s', exc)

    logging.info(
        'no system service detected; restart the server manually with meyectl startserver'
    )


def list_remote_branches(repo_url=None):
    remote = repo_url or _get_remote_url()
    if not remote:
        return []

    try:
        output = utils.call_subprocess(['git', '-C', str(REPO_ROOT), 'ls-remote', '--heads', remote])
    except Exception as exc:
        logging.warning('failed to list branches for %s: %s', remote, exc)
        return []

    branches = []
    for line in output.splitlines():
        try:
            _rev, ref = line.split('\t', 1)
            branches.append(ref.replace('refs/heads/', ''))
        except ValueError:
            continue

    return sorted(set(branches))


def get_source_update_status(repo_url=None, branch=None):
    if not _is_git_repo():
        return None

    try:
        current_branch = _git('rev-parse', '--abbrev-ref', 'HEAD')
    except Exception as exc:
        logging.warning('failed to detect current branch: %s', exc)
        return None

    target_branch = branch or current_branch
    remote = repo_url or _get_remote_url()
    remote_ref = None

    if remote:
        try:
            _git('fetch', remote, target_branch)
            remote_ref = 'FETCH_HEAD'
        except Exception as exc:
            logging.warning('failed to fetch updates from %s: %s', remote, exc)
    else:
        try:
            _git('fetch', '--all')
            remote_ref = f'origin/{target_branch}'
        except Exception as exc:
            logging.warning('failed to fetch updates: %s', exc)

    # Always compare HEAD (current position) with the remote target
    current_revision = _git('rev-parse', '--short', 'HEAD')

    update_revision = None
    if remote_ref:
        try:
            remote_revision = _git('rev-parse', '--short', remote_ref)
            # There's an update if remote is different from current HEAD
            if remote_revision != current_revision:
                update_revision = remote_revision
        except Exception as exc:
            logging.warning('failed to compare local and remote revisions: %s', exc)

    return {
        'update_version': f'{target_branch}@{update_revision}' if update_revision else None,
        'current_version': f'{current_branch}@{current_revision}',
        'branch': target_branch,
        'repo_url': remote,
    }


def perform_source_update(version=None, repo_url=None, branch=None):
    if not _is_git_repo():
        raise Exception('source update is not available because the install is not a git clone')

    branch = branch or (version.split('@')[0] if version else _git('rev-parse', '--abbrev-ref', 'HEAD'))
    remote = repo_url or _get_remote_url() or 'origin'

    logging.info('updating branch %s from source via %s...', branch, remote)

    _git('checkout', branch)
    _git('pull', '--ff-only', remote, branch)

    python_executable = str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable))

    utils.call_subprocess([python_executable, '-m', 'pip', 'install', '--upgrade', 'pip', 'wheel'])
    utils.call_subprocess(
        [python_executable, '-m', 'pip', 'install', '--upgrade', '--pre', '-e', str(REPO_ROOT)]
    )

    _restart_service_if_exists()

    return {'ok': True}


def get_all_versions():
    try:
        import platformupdate

    except ImportError:
        return []

    return platformupdate.get_all_versions()


def perform_update(version, repo_url=None, branch=None):
    logging.info(f'updating to version {version}...')

    source_status = get_source_update_status(repo_url=repo_url, branch=branch)
    if source_status:
        return perform_source_update(version, repo_url=repo_url, branch=branch)

    try:
        import platformupdate

    except ImportError:
        logging.error('updating is not available on this platform')

        raise Exception('updating is not available on this platform')

    # schedule the actual update for two seconds later,
    # since we want to be able to respond to the request right away
    ioloop.IOLoop.current().add_timeout(
        datetime.timedelta(seconds=2), platformupdate.perform_update, version=version
    )


def get_update_status(repo_url=None, branch=None):
    source_status = get_source_update_status(repo_url=repo_url, branch=branch)
    if source_status:
        return source_status

    versions = get_all_versions()
    current_version = motioneye.VERSION
    recent_versions = [v for v in versions if compare_versions(v, current_version) > 0]
    recent_versions.sort(key=cmp_to_key(compare_versions))
    update_version = recent_versions[-1] if recent_versions else None

    return {
        'update_version': update_version,
        'current_version': current_version,
        'branch': branch,
        'repo_url': repo_url,
    }
