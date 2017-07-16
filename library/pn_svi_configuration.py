#!/usr/bin/python
""" PN SVI Configuration """

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

import shlex

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = """
---
module: pn_svi_configuration
author: 'Pluribus Networks (devops@pluribusnetworks.com)'
description: Module to configure SVI.
svi csv file format: gateway_ip, vlan_id
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
    pn_switch:
      description:
        - Name of the switch on which this task is currently getting executed.
      required: True
      type: str
    pn_svi_data:
      description:
        - String containing SVI data parsed from csv file.
      required: False
      type: str
      default: ''
"""

EXAMPLES = """
- name: Configure SVI
  pn_svi_configuration:
    pn_cliusername: "{{ USERNAME }}"
    pn_clipassword: "{{ PASSWORD }}"
    pn_switch: "{{ inventory_hostname }}"
    pn_svi_data: "{{ lookup('file', '{{ svi_file }}') }}"
"""

RETURN = """
summary:
  description: It contains output of each configuration along with switch name.
  returned: always
  type: str
changed:
  description: Indicates whether the CLI caused changes on the target.
  returned: always
  type: bool
unreachable:
  description: Indicates whether switch was unreachable to connect.
  returned: always
  type: bool
failed:
  description: Indicates whether or not the execution failed on the target.
  returned: always
  type: bool
exception:
  description: Describes error/exception occurred while executing CLI command.
  returned: always
  type: str
task:
  description: Name of the task getting executed on switch.
  returned: always
  type: str
msg:
  description: Indicates whether configuration made was successful or failed.
  returned: always
  type: str
"""

CHANGED_FLAG = []


def pn_cli(module):
    """
    Generate the cli portion to launch the Netvisor cli.
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


def run_cli(module, cli):
    """
    Execute the cli command on the target node(s) and returns the output.
    :param module: The Ansible module to fetch input parameters.
    :param cli: The complete cli string to be executed on the target node(s).
    :return: Output or Error msg depending upon the response from cli else None.
    """
    results = []
    cli = shlex.split(cli)
    rc, out, err = module.run_command(cli)

    if out:
        return out
    if err:
        json_msg = {
            'switch': module.params['pn_switch'],
            'output': u'Operation Failed: {}'.format(' '.join(cli))
        }
        results.append(json_msg)
        module.exit_json(
            unreachable=False,
            failed=True,
            exception=err.strip(),
            summary=results,
            task='Configure SVI',
            msg='SVI configuration failed',
            changed=False
        )
    else:
        return 'Success'


def svi_configuration(module, ip_gateway, switch, vlan_id):
    """
    Method to configure SVI inerface in the switch..
    :param module: The Ansible module to fetch input parameters.
    :param ip_gateway: IP address for the default gateway
    :param switch: Name of switch.
    :param vlan_id: The vlan id to be assigned.
    :return: String describing whether interface got added or not.
    """
    global CHANGED_FLAG

    cli = pn_cli(module)
    clicopy = cli

    cli = clicopy
    cli += ' vrouter-show location %s format name' % switch
    cli += ' no-show-headers'
    vrouter_name = run_cli(module, cli).split()[0]

    cli = clicopy
    cli += ' vrouter-interface-show ip %s vlan %s ' % (ip_gateway, vlan_id)
    cli += ' format switch no-show-headers '
    existing_vrouter = run_cli(module, cli).split()
    existing_vrouter = list(set(existing_vrouter))

    if vrouter_name not in existing_vrouter:
        cli = clicopy
        cli += 'switch ' + switch
        cli += ' vrouter-interface-add vrouter-name ' + vrouter_name
        cli += ' vlan ' + vlan_id
        cli += ' ip ' + ip_gateway
        run_cli(module, cli)
        CHANGED_FLAG.append(True)
        return ' %s: Added vrouter interface with ip %s \n' % (
            switch, ip_gateway
        )
    else:
        return ''


def main():
    """ This section is for arguments parsing """
    module = AnsibleModule(
        argument_spec=dict(
            pn_cliusername=dict(required=False, type='str'),
            pn_clipassword=dict(required=False, type='str', no_log=True),
            pn_switch=dict(required=True, type='str'),
            pn_svi_data=dict(required=False, type='str', default=''),
        )
    )

    global CHANGED_FLAG
    results = []
    message = ''
    switch = module.params['pn_switch']

    svi_data = module.params['pn_svi_data']
    if svi_data:
        svi_data = svi_data.replace(' ', '')
        svi_data_list = svi_data.split('\n')
        for row in svi_data_list:
            if row.startswith('#'):
                continue
            else:
                elements = row.split(',')
                ip_gateway = elements.pop(0)
                vlan_id = elements.pop(0)

    message += svi_configuration(module, ip_gateway, switch, vlan_id)

    for line in message.splitlines():
        if line:
            results.append({
                'switch': module.params['pn_switch'],
                'output': line
            })

    # Exit the module and return the required JSON.
    module.exit_json(
        unreachable=False,
        msg='SVI configuration succeeded',
        summary=results,
        exception='',
        failed=False,
        changed=True if True in CHANGED_FLAG else False,
        task='Configure SVI'
    )

if __name__ == '__main__':
    main()
