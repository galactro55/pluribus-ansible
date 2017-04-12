#!/usr/bin/python
""" PN CLI VRRP L3 """

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

from ansible.module_utils.basic import AnsibleModule
import shlex

DOCUMENTATION = """
---
module: pn_ztp_vrrp_l3
author: 'Pluribus Networks (devops@pluribusnetworks.com)'
short_description: CLI command to configure VRRP - Layer 3 Setup
description: Virtual Router Redundancy Protocol (VRRP) - Layer 3 Setup
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
    pn_spine_list:
      description:
        - Specify list of Spine hosts
      required: False
      type: list
    pn_leaf_list:
      description:
        - Specify list of leaf hosts
      required: False
      type: list
    pn_csv_data:
      description:
        - String containing vrrp data parsed from csv file.
      required: False
      type: str
"""

EXAMPLES = """
    - name: VRRP L3 setup
      pn_ztp_vrrp_l3:
        pn_cliusername: "{{ USERNAME }}"
        pn_clipassword: "{{ PASSWORD }}"
        pn_spine_list: "{{ groups['spine'] }}"
        pn_leaf_list: "{{ groups['leaf'] }}"
        pn_csv_data: "{{ lookup('file', '{{ csv_file }}') }}"
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

CHANGED_FLAG = []


def pn_cli(module):
    """
    Method to generate the cli portion to launch the Netvisor cli.
    :param module: The Ansible module to fetch username and password.
    :return: The cli string for further processing
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
    Method to execute the cli command on the target node(s) and returns the
    output.
    :param module: The Ansible module to fetch input parameters.
    :param cli: The complete cli string to be executed on the target node(s).
    :return: Output/Error or Success message depending upon.
    the response from cli.
    """
    cli = shlex.split(cli)
    rc, out, err = module.run_command(cli)
    if out:
        return out

    if err:
        module.exit_json(
            error="1",
            failed=True,
            stderr=err.strip(),
            msg="Operation Failed: " + str(cli),
            changed=False
        )
    else:
        return 'Success'


def get_vrouter_name(module, switch_name):
    """
    Method to return name of the vrouter.
    :param module: The Ansible module to fetch input parameters.
    :param switch_name: Name of the switch for which to find the vrouter.
    :return: Vrouter name.
    """
    cli = pn_cli(module)
    cli += ' vrouter-show location ' + switch_name
    cli += ' format name no-show-headers '
    return run_cli(module, cli).split()[0]


def create_vlan(module, vlan_id, switch):
    """
    Method to create vlans.
    :param module: The Ansible module to fetch input parameters.
    :param vlan_id: vlan id to be created.
    :param switch: Name of the switch on which vlan creation will be executed.
    :return: String describing if vlan got created or if it already exists.
    """
    global CHANGED_FLAG
    cli = pn_cli(module)
    clicopy = cli
    cli += ' vlan-show format id no-show-headers '
    existing_vlan_ids = run_cli(module, cli).split()
    existing_vlan_ids = list(set(existing_vlan_ids))

    if vlan_id not in existing_vlan_ids:
        cli = clicopy
        cli += ' vlan-create id %s scope fabric ' % vlan_id
        run_cli(module, cli)
        CHANGED_FLAG.append(True)
        return ' %s: Vlan id %s with scope fabric created successfully \n' % (
            switch, vlan_id
        )

    else:
        return ' %s: Vlan id %s with scope fabric already exists \n' % (
            switch, vlan_id
        )


def create_vrouter(module, switch, vrrp_id, vnet_name):
    """
    Method to create vrouter and assign vrrp_id to the switches.
    :param module: The Ansible module to fetch input parameters.
    :param switch: The switch name on which vrouter will be created.
    :param vrrp_id: The vrrp_id to be assigned.
    :param vnet_name: The name of the vnet for vrouter creation.
    :return: String describing if vrouter got created or if it already exists.
    """
    global CHANGED_FLAG
    output = ''
    vrouter_name = str(switch) + '-vrouter'
    cli = pn_cli(module)
    cli += ' switch ' + switch
    clicopy = cli

    # Check if vrouter already exists
    cli += ' vrouter-show format name no-show-headers '
    existing_vrouter_names = run_cli(module, cli).split()

    # If vrouter doesn't exists then create it
    if vrouter_name not in existing_vrouter_names:
        cli = clicopy
        cli += ' vrouter-create name %s vnet %s hw-vrrp-id %s enable ' % (
            vrouter_name, vnet_name, vrrp_id)
        run_cli(module, cli)
        output = ' %s: Created vrouter with name %s \n' % (switch, vrouter_name)
        CHANGED_FLAG.append(True)
    else:
        cli = clicopy
        cli += ' vrouter-show name ' + vrouter_name
        cli += ' format hw-vrrp-id no-show-headers'
        hw_vrrp_id = run_cli(module, cli).split()[0]

        if hw_vrrp_id != vrrp_id:
            cli = clicopy
            cli += ' vrouter-modify name %s hw-vrrp-id %s ' % (vrouter_name,
                                                               vrrp_id)
            run_cli(module, cli)
            CHANGED_FLAG.append(True)

    return output


def create_vrouter_interface(module, switch, ip, vlan_id, vrrp_id,
                             ip_count, vrrp_priority):
    """
    Method to add vrouter interface and assign IP to it along with
    vrrp_id and vrrp_priority.
    :param module: The Ansible module to fetch input parameters.
    :param switch: The switch name on which interfaces will be created.
    :param ip: IP address to be assigned to vrouter interface.
    :param vlan_id: vlan_id to be assigned.
    :param vrrp_id: vrrp_id to be assigned.
    :param vrrp_priority: priority to be given(110 for active switch).
    :param ip_count: The value of fourth octet in the ip
    :return: String describing if vrouter interface got added or not.
    """
    global CHANGED_FLAG
    vrouter_name = get_vrouter_name(module, switch)
    ip_addr = ip.split('.')
    fourth_octet = ip_addr[3].split('/')
    subnet = fourth_octet[1]

    static_ip = ip_addr[0] + '.' + ip_addr[1] + '.' + ip_addr[2] + '.'
    ip_vip = static_ip + '1' + '/' + subnet
    ip2 = static_ip + ip_count + '/' + subnet

    cli = pn_cli(module)
    clicopy = cli
    cli += ' vrouter-interface-show vlan %s ip %s ' % (vlan_id, ip2)
    cli += ' format switch no-show-headers '
    existing_vrouter = run_cli(module, cli).split()
    existing_vrouter = list(set(existing_vrouter))

    if vrouter_name not in existing_vrouter:
        cli = clicopy
        cli += ' switch ' + switch
        cli += ' vrouter-interface-add vrouter-name ' + vrouter_name
        cli += ' ip ' + ip2
        cli += ' vlan %s if data ' % vlan_id
        run_cli(module, cli)
        output = ' %s: Added vrouter interface with ip %s to %s \n' % (
            switch, ip2, vrouter_name
        )
        CHANGED_FLAG.append(True)
    else:
        output = ' %s: Vrouter interface %s already exists for %s \n' % (
            switch, ip2, vrouter_name
        )

    cli = clicopy
    cli += ' vrouter-interface-show vrouter-name %s ip %s vlan %s ' % (
        vrouter_name, ip2, vlan_id
    )
    cli += ' format nic no-show-headers '
    eth_port = run_cli(module, cli).split()
    eth_port.remove(vrouter_name)

    cli = clicopy
    cli += ' vrouter-interface-show vlan %s ip %s vrrp-primary %s ' % (
        vlan_id, ip_vip, eth_port[0]
    )
    cli += ' format switch no-show-headers '
    existing_vrouter = run_cli(module, cli).split()
    existing_vrouter = list(set(existing_vrouter))

    if vrouter_name not in existing_vrouter:
        cli = clicopy
        cli += ' switch ' + switch
        cli += ' vrouter-interface-add vrouter-name ' + vrouter_name
        cli += ' ip ' + ip_vip
        cli += ' vlan %s if data vrrp-id %s ' % (vlan_id, vrrp_id)
        cli += ' vrrp-primary %s vrrp-priority %s ' % (eth_port[0],
                                                       vrrp_priority)
        run_cli(module, cli)
        output += ' %s: Added vrouter interface with ip %s to %s \n' % (
            switch, ip_vip, vrouter_name
        )
        CHANGED_FLAG.append(True)

    else:
        output += ' %s: Vrouter interface %s already exists for %s \n' % (
            switch, ip_vip, vrouter_name
        )

    return output


def create_cluster(module, switch, name, node1, node2):
    """
    Method to create a cluster between two switches.
    :param module: The Ansible module to fetch input parameters.
    :param switch: Name of the local switch.
    :param name: The name of the cluster to create.
    :param node1: First node of the cluster.
    :param node2: Second node of the cluster.
    :return: The output of run_cli() method.
    """
    global CHANGED_FLAG
    cli = pn_cli(module)
    clicopy = cli
    cli += ' switch %s cluster-show format name no-show-headers ' % node1
    cluster_list = run_cli(module, cli).split()
    if name not in cluster_list:
        cli = clicopy
        cli += ' switch %s cluster-create name %s ' % (switch, name)
        cli += ' cluster-node-1 %s cluster-node-2 %s ' % (node1, node2)
        if 'Success' in run_cli(module, cli):
            CHANGED_FLAG.append(True)
            return ' %s: %s created successfully \n' % (switch, name)
    else:
        return ' %s: %s already exists \n' % (switch, name)


def create_vrouter_without_vrrp(module, switch, vnet_name):
    """
    Method to create vrouter without assigning vrrp id to it.
    :param module: The Ansible module to fetch input parameters.
    :param switch: The switch name on which vrouter will be created.
    :param vnet_name: The name of the vnet for vrouter creation.
    :return: String describing if vrouter got created or if it already exists.
    """
    global CHANGED_FLAG
    vrouter_name = str(switch) + '-vrouter'
    cli = pn_cli(module)
    cli += ' switch ' + switch
    clicopy = cli

    # Check if vrouter already exists
    cli += ' vrouter-show format name no-show-headers '
    existing_vrouter_names = run_cli(module, cli).split()

    # If vrouter doesn't exists then create it
    if vrouter_name not in existing_vrouter_names:
        cli = clicopy
        cli += ' vrouter-create name %s vnet %s ' % (vrouter_name, vnet_name)
        run_cli(module, cli)
        output = ' %s: Created vrouter with name %s \n' % (switch, vrouter_name)
        CHANGED_FLAG.append(True)
    else:
        output = ' %s: Vrouter with name %s already exists \n' % (switch,
                                                                  vrouter_name)

    return output


def configure_vrrp_for_non_cluster_leafs(module, ip, non_cluster_leaf, vlan_id):
    """
    Method to configure vrrp for non-cluster switches.
    :param module: The Ansible module to fetch input parameters.
    :param ip: IP address for the default gateway
    :param non_cluster_leaf: Name of non-cluster leaf switch.
    :param vlan_id: The vlan id to be assigned.
    :return: String describing whether interfaces got added or not.
    """
    global CHANGED_FLAG
    vrouter_name = get_vrouter_name(module, non_cluster_leaf)

    ip_addr = ip.split('.')
    fourth_octet = ip_addr[3].split('/')
    subnet = fourth_octet[1]

    static_ip = ip_addr[0] + '.' + ip_addr[1] + '.' + ip_addr[2] + '.'
    ip_gateway = static_ip + '1' + '/' + subnet

    cli = pn_cli(module)
    clicopy = cli
    cli += ' vrouter-interface-show ip %s vlan %s ' % (ip_gateway, vlan_id)
    cli += ' format switch no-show-headers '
    existing_vrouter = run_cli(module, cli).split()
    existing_vrouter = list(set(existing_vrouter))

    if vrouter_name not in existing_vrouter:
        cli = clicopy
        cli += 'switch ' + non_cluster_leaf
        cli += ' vrouter-interface-add vrouter-name ' + vrouter_name
        cli += ' vlan ' + vlan_id
        cli += ' ip ' + ip_gateway
        run_cli(module, cli)
        CHANGED_FLAG.append(True)
        return ' %s: Added vrouter interface with ip %s on %s \n' % (
            non_cluster_leaf, ip_gateway, vrouter_name
        )

    else:
        return ' %s: Vrouter interface %s already exists on %s \n' % (
            non_cluster_leaf, ip_gateway, vrouter_name
        )


def configure_vrrp_for_clustered_switches(module, vrrp_id, vrrp_ip,
                                          active_switch, vlan_id, switch_list):
    """
    Method to configure vrrp interfaces for clustered leaf switches.
    :param module: The Ansible module to fetch input parameters.
    :param vrrp_id: The vrrp_id to be assigned.
    :param vrrp_ip: The vrrp_ip to be assigned.
    :param active_switch: The name of the active switch.
    :param vlan_id: vlan id to be assigned.
    :param switch_list: List of clustered switches.
    :return: The output of the configuration.
    """
    node1 = switch_list[0]
    node2 = switch_list[1]
    name = node1 + '-to-' + node2 + '-cluster'
    host_count = 1

    output = create_cluster(module, node2, name, node1, node2)
    output += create_vlan(module, vlan_id, node2)

    vnet_name = get_global_vnet_name(module)

    for switch in switch_list:
        output += create_vrouter(module, switch, vrrp_id, vnet_name)

    for switch in switch_list:
        host_count += 1
        vrrp_priority = '110' if switch == active_switch else '100'
        output += create_vrouter_interface(module, switch, vrrp_ip, vlan_id,
                                           vrrp_id, str(host_count),
                                           vrrp_priority)

    return output


def configure_vrrp_for_non_clustered_switches(module, vlan_id, ip,
                                              non_cluster_leaf):
    """
    Method to configure VRRP for non clustered leafs.
    :param module: The Ansible module to fetch input parameters.
    :param vlan_id: vlan id to be assigned.
    :param ip: Ip address to be assigned.
    :param non_cluster_leaf: Name of non-clustered leaf switch.
    :return: Output string of configuration.
    """
    vnet_name = get_global_vnet_name(module)
    output = create_vrouter_without_vrrp(module, non_cluster_leaf, vnet_name)
    output += create_vlan(module, vlan_id, non_cluster_leaf)
    output += configure_vrrp_for_non_cluster_leafs(module, ip,
                                                   non_cluster_leaf, vlan_id)
    return output


def configure_vrrp(module, csv_data):
    """
    Method to configure VRRP L3.
    :param module: The Ansible module to fetch input parameters.
    :param csv_data: String containing vrrp data passed from csv file.
    :return: Output string of configuration.
    """
    output = ''
    vnet_name = get_global_vnet_name(module)
    for switch in module.params['pn_new_spine_list']:
        output += create_vrouter_without_vrrp(module, switch, vnet_name)

    csv_data = csv_data.replace(" ", "")
    csv_data_list = csv_data.split('\n')
    # Parse csv file data and configure VRRP.
    for row in csv_data_list:
        elements = row.split(',')
        switch_list = []
        vlan_id = elements[0]
        vrrp_ip = elements[1]
        leaf_switch_1 = str(elements[2])
        if len(elements) > 5:
            leaf_switch_2 = str(elements[3])
            vrrp_id = elements[4]
            active_switch = str(elements[5])
            switch_list.append(leaf_switch_1)
            switch_list.append(leaf_switch_2)
            output += configure_vrrp_for_clustered_switches(module, vrrp_id,
                                                            vrrp_ip,
                                                            active_switch,
                                                            vlan_id,
                                                            switch_list)

        else:
            output += configure_vrrp_for_non_clustered_switches(module, vlan_id,
                                                                vrrp_ip,
                                                                leaf_switch_1)

    return output


def get_global_vnet_name(module):
    """
    Method to get global vnet name, required for vrouters creation.
    :param module: The Ansible module to fetch input parameters.
    :return: Global vnet name.
    """
    cli = pn_cli(module)
    cli += ' fabric-node-show format fab-name no-show-headers '
    fabric_name = list(set(run_cli(module, cli).split()))[0]
    return str(fabric_name) + '-global'


def main():
    """ This section is for arguments parsing """
    module = AnsibleModule(
        argument_spec=dict(
            pn_cliusername=dict(required=False, type='str'),
            pn_clipassword=dict(required=False, type='str', no_log=True),
            pn_new_spine_list=dict(required=False, type='list'),
            pn_leaf_list=dict(required=False, type='list'),
            pn_spine_list=dict(required=False, type='list'),
            pn_new_leaf_list=dict(required=False, type='list'),
            pn_csv_data=dict(required=True, type='str'),
        )
    )

    global CHANGED_FLAG
    message = configure_vrrp(module, module.params['pn_csv_data'])

    module.exit_json(
        stdout=message,
        error='0',
        failed=False,
        changed=True if True in CHANGED_FLAG else False
    )


if __name__ == '__main__':
    main()

