#!/usr/bin/python
""" PN FULL MESH VROUTER-PING TEST """

#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

import time
import shlex

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = """
---
module: pn_vrouter_ping_test
author: 'Pluribus Networks (devops@pluribusnetworks.com)'
short_description: CLI command to do full mesh vrouter-ping test
description:
    This script is a network testing module whose function is to
    perform a full mesh vrouter-ping test.
    It performs following steps:
        - Ping test
options:
    pn_cliusername:
        description:
          - Provide login username if user is not root.
        required: False
        type: str
    pn_clipassword:
      description:
        - Provide login password if user is not root.
      required: False
      type: str
"""

EXAMPLES = """
    - name: Full mesh vrouter-ping test
      pn_vrouter_ping_test:
        pn_cliusername: "{{ USERNAME }}"  # Cli username (value comes from cli_vault.yml).
        pn_clipassword: "{{ PASSWORD }}"  # Cli password (value comes from cli_vault.yml).
"""

RETURN = """
stdout:
  description: The set of responses for each command.
  returned: always
  type: str
changed:
  description: Indicates whether the CLI caused changes on the target.
  returned: always
  type: bool
failed:
  description: Indicates whether or not the execution failed on the target.
  returned: always
  type: bool
"""

def run_cli(module, cli):
    """
    Method to execute the cli command on the target node(s) and returns the
    output.
    :param module: The Ansible module to fetch input parameters.
    :param cli: The complete cli string to be executed on the target node(s).
    :return: Output/Error or Success msg depending upon the response from cli.
    """
    cli = shlex.split(cli)
    rc, out, err = module.run_command(cli)
    if out:
        return out

    if err:
        module.exit_json(
            error='1',
            failed=True,
            stderr=err.strip(),
            msg='Operation Failed: ' + str(cli),
            changed=False
        )
    else:
        return 'Success'


def pn_cli(module):
    """
    Method to generate the cli portion to launch the Netvisor cli.
    :param module: The Ansible module to fetch username and password.
    :return: The cli string for further processing.
    """
    username = module.params['pn_cliusername']
    password = module.params['pn_clipassword']

    if username and password:
        cli = '/usr/bin/cli --quiet --user %s:%s ' % (username, password)
    else:
        cli = '/usr/bin/cli --quiet '

    return cli


def run_ping_command(module, vrouter, ip_addr):
    """
    Method to run ping command and check the status.
    :param module: The Ansible module to fetch input parameters.
    :param vrouter: The source vrouter from where the ping test is run.
    :param ip: The destination ip for ping test.
    :return: Output/Error or Success msg depending upon the status of ping.
    """
    cli = pn_cli(module)
    cli += 'vrouter-ping vrouter-name %s host-ip %s count 1' % (vrouter, ip_addr)
    message = run_cli(module, cli)

    if ('unreachable' in message or 'Unreachable' in message or
            '100% packet loss' in message):
        message = 'vrouter-ping failed from vrouter %s to ip %s ' % (
            vrouter, ip_addr)
        module.exit_json(
            unreachable=False,
            failed=True,
            exception=message,
            stderr=message,
            summary=[{
                'vrouter': vrouter,
                'output': message,
            }],
            task='Full mesh vrouter-ping test',
            msg='Vrouter-ping failed',
            changed=False
        )
    else:
        return '%s:vrouter-ping successful from vrouter %s to ip %s \n' % (
            vrouter, vrouter, ip_addr)


def vrouter_ping_test(module):
    """
    This method is used to find out all the assigned ips and do a vrouter-ping
    test to check the connectivity from all vrouters to these ips.
    (Note: The slave switch is not supposed to ping Vip)
    :param module: The Ansible module to fetch input parameters.
    :return: It returns the status of all ping test.
    """
    vrouter_ip_list = []
    cli = pn_cli(module)
    clicopy = cli
    message = ''

    cli += ' vrouter-show format name no-show-headers '
    vrouter_list = run_cli(module, cli).split()

    for vrouter in vrouter_list:
        cli = clicopy
        cli += ' vrouter-interface-show vrouter-name %s' % vrouter
        cli += ' format l3-port no-show-headers'
        port_list = run_cli(module, cli).split()
        port_list = list(set(port_list))
        port_list.remove(vrouter)

        for port in port_list:
            cli = clicopy
            cli += ' vrouter-interface-show vrouter-name %s l3-port %s ' % (
                vrouter, port)
            cli += ' format ip no-show-headers'
            ip_addr = run_cli(module, cli).split()
            ip_addr = list(set(ip_addr))
            ip_addr.remove(vrouter)
            vrouter_ip_list.append(ip_addr[0])

    for vrouter in vrouter_list:
        for ip_addr in vrouter_ip_list:
            ip_addr = ip_addr.split('/')[0]
            message += run_ping_command(module, vrouter, ip_addr)
            time.sleep(1)

    cli = clicopy
    cli += ' vrouter-interface-show vrrp-state slave'
    cli += ' format switch,ip no-show-headers'
    vrrp_ip_list = run_cli(module, cli).split()

    if len(vrrp_ip_list) > 0 and 'Success' not in vrrp_ip_list:
        while len(vrrp_ip_list) > 0:
            slave = vrrp_ip_list.pop(0)
            vrrp_ip = vrrp_ip_list.pop(0)
            vrouter_list_without_slave = [vrouter for vrouter in vrouter_list if vrouter != slave]
            for vrouter in vrouter_list_without_slave:
                vrrp_ip = vrrp_ip.split('/')[0]
                message += run_ping_command(module, vrouter, vrrp_ip)
                time.sleep(1)

    return message


def main():
    """ This section is for arguments parsing """
    module = AnsibleModule(argument_spec=dict(
        pn_cliusername=dict(required=False, type='str'),
        pn_clipassword=dict(required=False, type='str', no_log=True),
        )
                          )

    results = []
    message = vrouter_ping_test(module)
    message = message.splitlines()

    for line in message:
        line = line.split(':')
        json_msg = {
            'vrouter': line[0],
            'output': line[1].strip(),
            }
        results.append(json_msg)

    module.exit_json(
        unreachable=False,
        msg='Vrouter ping test successful',
        summary=results,
        exception='',
        task='Full mesh vrouter-ping test',
        failed=False,
    )


if __name__ == '__main__':
    main()
