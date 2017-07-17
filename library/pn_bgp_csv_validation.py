#!/usr/bin/python
""" PN BGP CSV Validation """

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

import socket
import re

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = """
---
module: pn_bgp_csv_validation
author: 'Pluribus Networks (devops@pluribusnetworks.com)'
description: Module to validate bgp configuration csv file.
    Csv file format: switch_name, local_port, interface_ip(with subnet), bgp_as, remote_ip(without subnet), remote_as
    Csv file should not be empty. This module validates the given csv file.
options:
    pn_bgp_data:
      description: String containing vlag config data parsed from csv file.
      required: True
      type: str
    pn_switch_list:
      description: Specify list of all switches.
      required: True
      type: list
"""

EXAMPLES = """
- name: Validate bgp csv file
  pn_bgp_csv_validation:
    pn_bgp_data: "{{ lookup('file', '{{ csv_file }}') }}"
    pn_switch_list: "{{ groups['switch'] }}"
"""

RETURN = """
msg:
  description: It contains output of each validation.
  returned: always
  type: str
changed:
  description: Indicates whether the validation caused changes on the target.
  returned: always
  type: bool
unreachable:
  description: Empty string.
  returned: always
  type: bool
failed:
  description: Indicates if csv validation failed or not.
  returned: always
  type: bool
exception:
  description: Empty string.
  returned: always
  type: str
task:
  description: Name of the task getting executed.
  returned: always
  type: str
summary:
  description: Indicates whether csv file is valid or invalid.
  returned: always
  type: str
"""


def main():
    """ This section is for arguments parsing """
    module = AnsibleModule(
        argument_spec=dict(
            pn_bgp_data=dict(required=True, type='str'),
            pn_switch_list=dict(required=True, type='list'),
        )
    )

    output = ''
    line_count = 0
    existing_interface_ip = []
    existing_remote_ip = []

    bgp_data = module.params['pn_bgp_data'].replace(' ', '')
    if bgp_data:
        bgp_data_list = bgp_data.split('\n')
        for row in bgp_data_list:
            row = row.strip()
            line_count += 1

            if row.startswith('#'):
                # Skip comments which starts with '#'
                continue
            else:
                elements = row.split(',')
                if len(elements) == 6:
                    switch_name = elements[0]
                    local_port = elements[1]
                    interface_ip = elements[2]
                    bgp_as = elements[3]
                    remote_ip = elements[4]
                    remote_as = elements[5]

                    if (not switch_name or not local_port or not interface_ip or
                            not bgp_as or not remote_ip or not remote_as):
                        output += 'Invalid entry at line number {}\n'.format(
                            line_count
                        )
                    else:
                        # Local switch name validation
                        if (re.match("^[a-zA-Z0-9_.:-]+$", switch_name) is
                                None or switch_name not in
                                module.params['pn_switch_list']):
                            output += 'Invalid local switch name {} '.format(
                                switch_name)
                            output += 'at line number {}\n'.format(line_count)

                        # Local port number validation
                        if (not local_port.isdigit() or
                                int(local_port) not in range(1, 105)):
                            output += 'Invalid port {} '.format(port)
                            output += 'at line number {}\n'.format(
                                line_count)

                        # INTERFACE IP address validation
                        try:
                            if '/' not in interface_ip:
                                raise socket.error
                            else:
                                address_with_subnet = interface_ip.split('/')
                                address = address_with_subnet[0]
                                subnet = address_with_subnet[1]
                                dot_count = address.count('.')
                                if dot_count != 3 or address in existing_interface_ip:
                                    raise socket.error

                                socket.inet_aton(address)
                                if (not subnet.isdigit() or
                                        int(subnet) not in range(1, 33)):
                                    raise socket.error

                                existing_interface_ip.append(address)
                        except socket.error:
                            output += 'Invalid interface ip {} '.format(interface_ip)
                            output += 'at line number {}. '.format(line_count)
                            output += 'Note: Format of interface_ip -> x.x.x.x/subnet\n'

                        # REMOTE IP address validation
                        try:
                            if '/' in remote_ip:
                                raise socket.error
                            else:
                                address = remote_ip
                                dot_count = address.count('.')
                                if dot_count != 3 or address in existing_remote_ip:
                                    raise socket.error

                                socket.inet_aton(address)

                                existing_remote_ip.append(address)
                        except socket.error:
                            output += 'Invalid remote ip {} '.format(remote_ip)
                            output += 'at line number {}. '.format(line_count)
                            output += 'Note: Format of remote_ip -> x.x.x.x(without subnet)\n'

                        # BGP-AS validation
                        if (not bgp_as.isdigit()):
                            output += 'Invalid bgp-as {} '.format(bgp_as)
                            output += 'at line number {}\n'.format(
                                line_count)

                        # REMOTE-AS validation
                        if (not remote_as.isdigit()):
                            output += 'Invalid remote-as {} '.format(remote_as)
                            output += 'at line number {}\n'.format(
                                line_count)
                else:
                    output += 'Invalid entry at line number {}\n'.format(
                        line_count)
    else:
        output += 'Csv file should not be empty\n'

    if not output:
        msg = 'Valid csv file'
        failed_flag = False
    else:
        msg = 'Invalid csv file'
        failed_flag = True

    module.exit_json(
        unreachable=False,
        msg=output,
        summary=msg,
        exception='',
        failed=failed_flag,
        changed=False,
        task='Validate bgp csv file'
    )

if __name__ == '__main__':
    main()

