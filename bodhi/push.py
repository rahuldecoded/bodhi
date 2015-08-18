# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""
The tool for triggering updates pushes.
"""

import click

from collections import defaultdict
from fedora.client import BodhiClient

import bodhi.notifications


@click.command()
@click.option('--releases', help='Push updates for specific releases')
@click.option('--type', default=None, help='Push a specific type of update',
        type=click.Choice(['security', 'bugfix', 'enhancement', 'newpackage']))
@click.option('--request', default='testing,stable',
        help='Push updates with a specific request (default: testing,stable)',
        type=click.Choice(['testing', 'stable', 'unpush']))
@click.option('--builds', help='Push updates for specific builds')
@click.option('--username', envvar='USERNAME')
@click.option('--password', prompt=True, hide_input=True)
@click.option('--staging', help='Use the staging bodhi instance',
              is_flag=True, default=False)
def push(username, password, **kwargs):
    client = BodhiClient(username=username, password=password,
                         staging=kwargs['staging'])

    # Gather the list of updates based on the query parameters
    # Since there's currently no simple way to get a list of all updates with
    # any request, we'll take a comma/space-delimited list of them and query
    # one at a time.
    releases = defaultdict(defaultdict(list))  # release->request->updates
    num_updates = 0

    requests = kwargs['request'].replace(',', ' ').split(' ')
    del(kwargs['request'])
    for request in requests:
        resp = client.query(request=request, **kwargs)
        for update in resp.updates:
            num_updates += 1
            for build in update.builds:
                releases[update.release.name][request].append(build.nvr)

        # Write out a file that releng uses to pass to sigul for signing
        # TODO: in the future we should integrate signing into the workflow
        for release in releases:
            output_filename = request.title() + '-' + release
            click.echo(output_filename + '\n==========')
            with file(output_filename, 'w') as out:
                for build in releases[release][request]:
                    out.write(build + '\n')
                    click.echo(build)

    doit = raw_input('Push these %d updates? (y/n)' % num_updates).lower().strip()
    if doit == 'y':
        click.echo('Sending masher.start fedmsg')
        bodhi.notifications.init()
        bodhi.notifications.publish(topic='masher.start',
                msg=dict(updates=list(updates)),
                agent=username)
    else:
        click.echo('Aborting push')


if __name__ == '__main__':
    push()
