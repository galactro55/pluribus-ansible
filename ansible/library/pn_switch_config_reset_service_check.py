#!/usr/bin/python
""" PN CLI Switch Config Reset """

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
module: pn_switch_config_reset
author: 'Pluribus Networks (devops@pluribusnetworks.com)'
version: 1
short_description: CLI command to reset a switch.
description:
    This module will reset a switch by running switch-config-reset command.
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
- name: Switch config reset
  pn_switch_config_reset:
    pn_cliusername: "{{ USERNAME }}"
    pn_clipassword: "{{ PASSWORD }}"
"""

RETURN = """
msg:
  description: String describing if switch reset was successful or not.
  returned: always
  type: str
changed:
  description: Indicates whether the CLI caused changes on the target.
  returned: always
  type: bool
"""

def run_cli(module, cli):
    """
    Method to execute the cli command on the target node(s) and returns the
    output.
    :param module: The Ansible module to fetch input parameters.
    :param cli: The complete cli string to be executed on the target node(s).
    :return: Output msg depending upon the response from cli.
    """
    cli = shlex.split(cli)
    rc, out, err = module.run_command(cli)
    return out


def check_service_status(module, service_name):
    """
    Method to check service running status.
    :param module: The Ansible module to fetch input parameters.
    :param service_name: The service for which the status to be checked.
    :return: Output msg depending upon the response from cli.
    """
    cli = 'service ' + service_name + ' status'
    return run_cli(module, cli)


def service_start(module, service_name):
    """
    Method to start the service.
    :param module: The Ansible module to fetch input parameters.
    :param service_name: The service for which the status to be checked.
    :return: Output msg depending upon the response from cli.
    """
    cli = 'service ' + service_name + ' start'
    return run_cli(module, cli)


def service_checks(module, epocs, service_list):
    """
    Method to check the status of the services and start if the 
    service is down.
    :param module: The Ansible module to fetch input parameters.
    :param epocs: Max no. of tries to start a service.
    :param service_list: The list of the services.
    :return: Output msg depending upon the services status.
    """
    if epocs == 0:
        return "Problem with services %s. " % service_list
    else:
        bad_service_list = []
        for service in service_list:
            output = check_service_status(module, service)
            output = output.strip()
             
            if output == 'online' or 'is running' in output:
                pass
            else:
                bad_service_list.append(service)
        if len(bad_service_list) == 0:
            return "all services working"
        else:
            for service in bad_service_list:
                service_start(module, service)

        return service_checks(module, epocs - 1, bad_service_list)


def wrapper_for_service_check(func):
    """
    Wrapper function to check for the services whenever 
    switch-reset function is called.
    :param func: The name of the switch_reset_function.
    :return: Helper function.
    """
    def main_wrapper(module, epocs, service_list):
        output = service_checks(module, epocs, service_list)
        if output == 'all services working':
            output = func(module)
            return "switch-config-reset is done"
        else:
            return output + "Please checks the services"

    return main_wrapper


@wrapper_for_service_check
def switch_config_reset(module):
    """
    Method to perform switch-config-reset.
    :param module: The Ansible module to fetch input parameters.
    :return: Output msg depending upon the response of the cli.
    """
    current_switch = module.params['pn_current_switch']
    username = module.params['pn_cliusername']
    password = module.params['pn_clipassword']
    if username and password:
        cli = '/usr/bin/cli --quiet --user %s:%s ' % (username, password)
    else:
        cli = '/usr/bin/cli --quiet '

    cli += ' --no-login-prompt switch-config-reset '

    cli = shlex.split(cli)
    rc, out, err = module.run_command(cli)

    if err:
        if 'User authorization failed' in err:
            module.exit_json(
                summary=[{
                    'switch': current_switch,
                    'output': 'Switch has been already reset.',
                }],
                failed=False,
                changed=False,
                exception='',
                task='Reset all switches',
                msg='Switch has been already reset.'
            )
        elif 'nvOSd not running' in err:
            stdout_msg = 'Switch has been just reset. '
            stdout_msg += 'Please wait for nvOSd to reboot completely.'
            module.exit_json(
                summary=[{
                    'switch': current_switch,
                    'output': stdout_msg,
                }],
                failed=False,
                changed=False,
                exception='',
                task='Reset all switches',
                msg=stdout_msg
            )
        else:
            module.exit_json(
                summary=[{
                    'switch': current_switch,
                    'output': 'Operation Failed: ' + str(cli),
                }],
                failed=True,
                exception=err.strip(),
                msg='Operation Failed: ' + str(cli),
                changed=False,
                task='Reset all switches'
            )
    else:
        module.exit_json(
            summary=[{
                'switch': current_switch,
                'output': 'Switch config reset completed successfully.',
            }],
            failed=False,
            changed=True,
            exception='',
            task='Reset all switches',
            msg='Switch config reset completed successfully.'
        )


def main():
    """ This section is for arguments parsing """
    module = AnsibleModule(
        argument_spec=dict(
            pn_cliusername=dict(required=False, type='str'),
            pn_clipassword=dict(required=False, type='str', no_log=True),
            pn_current_switch=dict(required=False, type='str'),
        )
    )

    iterate = 2
    service_list = ['svc-nvOSd', 'svc-nvOS_mon', 'nvOS-ovsdb']
    output = switch_config_reset(module, iterate, service_list)

    module.exit_json(
        summary=[{
            'switch': module.params['pn_current_switch'],
            'output': output,
        }],
        failed=True,
        changed=False,
        exception='',
        task='Reset all switches',
        msg='Switch config reset completed unsuccessfully.'
        )


if __name__ == '__main__':
    main()
