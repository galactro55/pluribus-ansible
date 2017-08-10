#!/usr/bin/python
""" PN CLI Layer2 Zero Touch Provisioning (ZTP) """

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
module: pn_l2_ztp
author: 'Pluribus Networks (devops@pluribusnetworks.com)'
short_description: CLI command to configure L2 zero touch provisioning.
description:
    Zero Touch Provisioning (ZTP) allows you to provision new switches in your
    network automatically, without manual intervention.
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
        - Specify list of Spine hosts.
      required: False
      type: list
    pn_leaf_list:
      description:
        - Specify list of leaf hosts.
      required: False
      type: list
    pn_update_fabric_to_inband:
      description:
        - Flag to indicate if fabric network should be updated to in-band.
      required: False
      default: False
      type: bool
    pn_stp:
      description:
        - Flag to enable STP at the end.
      required: False
      default: False
      type: bool
"""

EXAMPLES = """
- name: Zero Touch Provisioning - Layer2 setup
  pn_l2_ztp:
    pn_cliusername: "{{ USERNAME }}"
    pn_clipassword: "{{ PASSWORD }}"
    pn_spine_list: "{{ groups['spine'] }}"
    pn_leaf_list: "{{ groups['leaf'] }}"
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
    results = []
    if out:
        return out

    if err:
        json_msg = {
            'switch': '',
            'output': u'Operation Failed: {}'.format(' '.join(cli))
        }
        results.append(json_msg)
        module.exit_json(
            unreachable=False,
            failed=True,
            exception=err.strip(),
            summary=results,
            task='Configure L2 ZTP (Auto vLags)',
            msg='L2 ZTP configuration failed',
            changed=False
        )
    else:
        return 'Success'


def modify_stp(module, modify_flag):
    """
    Method to enable/disable STP (Spanning Tree Protocol) on all switches.
    :param module: The Ansible module to fetch input parameters.
    :param modify_flag: Enable/disable flag to set.
    :return: The output of run_cli() method.
    """
    global CHANGED_FLAG
    output = ''
    cli = pn_cli(module)
    clicopy = cli

    for switch in (module.params['pn_spine_list'] +
                   module.params['pn_leaf_list']):
        cli = clicopy
        cli += ' switch %s stp-show format enable ' % switch
        current_state = run_cli(module, cli).split()[1]
        if current_state != 'yes':
            cli = clicopy
            cli += ' switch ' + switch
            cli += ' stp-modify ' + modify_flag
            if 'Success' in run_cli(module, cli):
                output += ' %s: STP enabled \n' % switch
                CHANGED_FLAG.append(True)
        else:
            output += ' %s: STP is already enabled \n' % switch

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

    return ' %s: Created %s \n' % (switch, name)


def get_ports(module, switch, peer_switch):
    """
    Method to figure out connected ports between two switches.
    :param module: The Ansible module to fetch input parameters.
    :param switch: Name of the local switch.
    :param peer_switch: Name of the connected peer switch.
    :return: List of connected ports.
    """
    cli = pn_cli(module)
    cli += ' switch %s port-show hostname %s' % (switch, peer_switch)
    cli += ' format port no-show-headers '
    return run_cli(module, cli).split()


def create_trunk(module, switch, name, ports):
    """
    Method to create a trunk on a switch.
    :param module: The Ansible module to fetch input parameters.
    :param switch: Name of the local switch.
    :param name: The name of the trunk to create.
    :param ports: List of connected ports.
    :return: The output of run_cli() method.
    """
    global CHANGED_FLAG
    cli = pn_cli(module)
    clicopy = cli
    cli += ' switch %s trunk-show format name no-show-headers ' % switch
    trunk_list = run_cli(module, cli).split()
    if name not in trunk_list:
        cli = clicopy
        ports_string = ','.join(ports)
        cli += ' switch %s trunk-create name %s ' % (switch, name)
        cli += ' ports %s ' % ports_string
        run_cli(module, cli)
        CHANGED_FLAG.append(True)

    return ' %s: Created trunk %s \n' % (switch, name)


def find_non_clustered_leafs(module, leaf_list):
    """
    Method to find leafs which are not part of any cluster.
    :param module: The Ansible module to fetch input parameters.
    :param leaf_list: The list of leaf switches.
    :return: List of non clustered leaf switches.
    """
    non_clustered_leafs = []
    cli = pn_cli(module)
    cli += ' cluster-show format cluster-node-1,cluster-node-2 '
    cli += ' no-show-headers '
    clustered_nodes = run_cli(module, cli).split()

    for leaf in leaf_list:
        if leaf not in clustered_nodes:
            non_clustered_leafs.append(leaf)

    return non_clustered_leafs


def create_vlag(module, switch, name, peer_switch, port, peer_port):
    """
    Method to create virtual link aggregation groups.
    :param module: The Ansible module to fetch input parameters.
    :param switch: Name of the local switch.
    :param name: The name of the vlag to create.
    :param peer_switch: Name of the peer switch.
    :param port: Name of the trunk on local switch.
    :param peer_port: Name of the trunk on peer switch.
    :return: String describing if vlag got created or if it already exists.
    """
    global CHANGED_FLAG
    cli = pn_cli(module)
    clicopy = cli
    cli += ' switch %s vlag-show format name no-show-headers ' % switch
    vlag_list = run_cli(module, cli).split()
    if name not in vlag_list:
        cli = clicopy
        cli += ' switch %s vlag-create name %s port %s ' % (switch, name, port)
        cli += ' peer-switch %s peer-port %s mode active-active' % (peer_switch,
                                                                    peer_port)
        if 'Success' in run_cli(module, cli):
            CHANGED_FLAG.append(True)

    return ' %s: Configured vLag %s \n' % (switch, name)


def configure_trunk(module, cluster_node, switch_list):
    """
    Method to configure trunk vlags.
    :param module: The Ansible module to fetch input parameters.
    :param cluster_node: The node from which lag needs to be created.
    :param switch_list: The list of connected switches to find
    physical linked port.
    :return: Name of the trunk that got created.
    """
    switch_names = ''
    src_ports = []
    for switch in switch_list:
        src_ports += get_ports(module, cluster_node, switch)
        switch_names += str(switch)

    src_ports = list(set(src_ports))
    src_ports = filter(lambda l: l != 'Success', src_ports)
    name = cluster_node + '-to-' + switch_names
    if len(name) > 59:
        name = name[:59]

    output = create_trunk(module, cluster_node, name, src_ports)
    return output + name


def configure_trunk_vlag_for_clustered_leafs(module, non_clustered_leafs,
                                             spine_list):
    """
    Method to create clusters, trunks and vlag for the switches having
    physical links (clustered leafs).
    :param module: The Ansible module to fetch input parameters.
    :param non_clustered_leafs: The list of non clustered leaf switches.
    :param spine_list: The list of spine switches.
    :return: Output of create_cluster() and create_vlag() methods.
    """
    cli = pn_cli(module)
    clicopy = cli
    output = ''
    non_clustered_leafs_count = 0
    while non_clustered_leafs_count == 0:
        if len(non_clustered_leafs) == 0:
            non_clustered_leafs_count += 1
        else:
            node1 = non_clustered_leafs[0]
            non_clustered_leafs.remove(node1)

            cli = clicopy
            cli += ' switch %s lldp-show ' % node1
            cli += ' format sys-name no-show-headers '
            system_names = run_cli(module, cli).split()
            system_names = list(set(system_names))

            cli = clicopy
            cli += ' switch %s fabric-node-show ' % node1
            cli += ' format name no-show-headers '
            nodes_in_fabric = run_cli(module, cli).split()
            nodes_in_fabric = list(set(nodes_in_fabric))

            for system in system_names:
                if system not in nodes_in_fabric:
                    system_names.remove(system)

            terminate_flag = 0
            node_count = 0
            while (node_count < len(system_names)) and (terminate_flag == 0):
                node2 = system_names[node_count]
                if node2 in non_clustered_leafs:
                    # Cluster creation
                    cluster_name = node1 + '-to-' + node2 + '-cluster'
                    if len(cluster_name) > 59:
                        cluster_name = cluster_name[:59]

                    output += create_cluster(module, node2, cluster_name,
                                             node1, node2)

                    non_clustered_leafs.remove(node2)

                    # Trunk creation (leaf to spines)
                    trunk_message1 = configure_trunk(module, node1,
                                                     spine_list).split('\n')
                    trunk_message2 = configure_trunk(module, node2,
                                                     spine_list).split('\n')
                    trunk_name1 = trunk_message1[1]
                    trunk_name2 = trunk_message2[1]
                    output += trunk_message1[0] + '\n'
                    output += trunk_message2[0] + '\n'
                    # Vlag creation (leaf to spines)
                    vlag_name = node1 + '-' + node2 + '-to-' + 'spine'
                    if len(vlag_name) > 59:
                        vlag_name = vlag_name[:59]

                    output += create_vlag(module, node1, vlag_name, node2,
                                          trunk_name1, trunk_name2)

                    leafs_list = [node1, node2]
                    spine1 = str(spine_list[0])
                    spine2 = str(spine_list[1])

                    # Trunk creation (spine to leafs)
                    trunk_message1 = configure_trunk(module, spine1,
                                                     leafs_list).split('\n')
                    trunk_message2 = configure_trunk(module, spine2,
                                                     leafs_list).split('\n')
                    trunk_name1 = trunk_message1[1]
                    trunk_name2 = trunk_message2[1]
                    output += trunk_message1[0] + '\n'
                    output += trunk_message2[0] + '\n'

                    # Vlag creation (spine to leafs)
                    name = 'spine-to-' + node1 + '-' + node2
                    if len(name) > 59:
                        name = name[:59]

                    output += create_vlag(module, spine1, name, spine2,
                                          trunk_name1, trunk_name2)

                    terminate_flag += 1

                node_count += 1
    return output


def configure_trunk_non_clustered_leafs(module, non_clustered_leafs,
                                        spine_list):
    """
    Method to create clusters, trunks and vlag for non clustered leafs.
    :param module: The Ansible module to fetch input parameters.
    :param non_clustered_leafs: The list of all non clustered leaf switches.
    :param spine_list: The list of all spine switches.
    :return: Output of configure_trunk() method.
    """
    output = ''
    for leaf in non_clustered_leafs:
        # Trunk creation (leaf to spines)
        trunk_message = configure_trunk(module, leaf, spine_list).split('\n')
        output += trunk_message[0] + '\n'

        spine1 = str(spine_list[0])
        spine2 = str(spine_list[1])

        # Trunk creation (spine to leafs)
        trunk_message1 = configure_trunk(module, spine1, [leaf]).split('\n')
        trunk_message2 = configure_trunk(module, spine2, [leaf]).split('\n')
        trunk_name1 = trunk_message1[1]
        trunk_name2 = trunk_message2[1]
        output += trunk_message1[0] + '\n'
        output += trunk_message2[0] + '\n'

        # Vlag creation (spine to leafs)
        name = 'spine-to-' + leaf
        if len(name) > 59:
            name = name[:59]

        output += create_vlag(module, spine1, name, spine2, trunk_name1,
                              trunk_name2)

    return output


def configure_auto_vlag(module):
    """
    Method to create and configure vlag.
    :param module: The Ansible module to fetch input parameters.
    :return: String describing output of configuration.
    """
    spine_list = module.params['pn_spine_list']
    leaf_list = module.params['pn_leaf_list']
    spine1 = spine_list[0]
    spine2 = spine_list[1]

    # Create cluster between two spines.
    output = create_cluster(module, spine1, 'spine-cluster', spine1, spine2)

    # Configure trunk, vlag for clustered leaf switches.
    output += configure_trunk_vlag_for_clustered_leafs(module,
                                                       list(leaf_list),
                                                       spine_list)

    # Configure trunk, vlag for non clustered leaf switches.
    non_clustered_leafs = find_non_clustered_leafs(module, leaf_list)
    output += configure_trunk_non_clustered_leafs(module, non_clustered_leafs,
                                                  spine_list)
    return output


def update_fabric_network_to_inband(module):
    """
    Method to update fabric network type to in-band
    :param module: The Ansible module to fetch input parameters.
    :return: The output of run_cli() method.
    """
    global CHANGED_FLAG
    output = ''
    cli = pn_cli(module)
    clicopy = cli

    for switch in (module.params['pn_spine_list'] +
                   module.params['pn_leaf_list']):
        cli = clicopy
        cli += ' fabric-info format fabric-network '
        fabric_network = run_cli(module, cli).split()[1]
        if fabric_network != 'in-band':
            cli = clicopy
            cli += ' switch ' + switch
            cli += ' fabric-local-modify fabric-network in-band '
            if 'Success' in run_cli(module, cli):
                CHANGED_FLAG.append(True)

        output += ' %s: Updated fabric network to in-band \n' % switch

    return output


def main():
    """ This section is for arguments parsing """
    module = AnsibleModule(
        argument_spec=dict(
            pn_cliusername=dict(required=False, type='str'),
            pn_clipassword=dict(required=False, type='str', no_log=True),
            pn_spine_list=dict(required=False, type='list'),
            pn_leaf_list=dict(required=False, type='list'),
            pn_update_fabric_to_inband=dict(required=False, type='bool',
                                            default=False),
            pn_stp=dict(required=False, type='bool', default=False),
        )
    )

    global CHANGED_FLAG

    # L2 setup (auto vLags).
    message = configure_auto_vlag(module)

    # Update fabric network to in-band if flag is True.
    if module.params['pn_update_fabric_to_inband']:
        message += update_fabric_network_to_inband(module)

    # Enable STP if flag is True.
    if module.params['pn_stp']:
        message += modify_stp(module, 'enable')

    results = []
    switch_list = module.params['pn_spine_list'] + module.params['pn_leaf_list']

    for switch in switch_list:
        replace_string = switch + ': '
        for line in message.splitlines():
            if replace_string in line:
                json_msg = {
                    'switch': switch,
                    'output': (line.replace(replace_string, '')).strip()
                }
                results.append(json_msg)

    # Exit the module and return the required JSON.
    module.exit_json(
        unreachable=False,
        msg='L2 ZTP configuration succeeded',
        summary=results,
        exception='',
        failed=False,
        changed=True if True in CHANGED_FLAG else False,
        task='Configure L2 ZTP (Auto vLags)'
    )

if __name__ == '__main__':
    main()

