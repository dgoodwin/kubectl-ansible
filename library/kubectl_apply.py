import os
import json
import subprocess
import tempfile
import yaml

from ansible.module_utils.basic import AnsibleModule, BOOLEANS

class KubectlRunner(object):

    def __init__(self, kubeconfig):
        self.kubeconfig = kubeconfig

    # following approach from lib_openshift
    def run(self, cmds, input_data):
        ''' Actually executes the command. This makes mocking easier. '''
        curr_env = os.environ.copy()
        curr_env.update({'KUBECONFIG': self.kubeconfig})
        proc = subprocess.Popen(cmds,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=curr_env)

        # TODO: encode here was required on Python 3, watchout for 2:
        stdout, stderr = proc.communicate(input_data.encode())
        return proc.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')


class KubectlApplier(object):
    def __init__(self, kubeconfig=None, namespace=None, inline=None, debug=None):
        self.kubeconfig = kubeconfig
        self.namespace = namespace
        self.inline = inline

        # Loads as a dict, convert to a json string for piping to kubectl:
        #self.inline = json.dumps(inline)

        self.cmds = ["kubectl", "apply", "-f", "-"]
        self.cmd_runner = KubectlRunner(self.kubeconfig)

        self.changed = False
        self.debug_lines = []
        self.stdout_lines = []
        self.stderr_lines = []

    def run(self):
        self.debug_lines.append('Using inline input: %s' % self.inline)
        exit_code, stdout, stderr = self.cmd_runner.run(self.cmds, self.inline)
        if stdout != '':
            self.stdout_lines.extend(stdout.split('\n'))
        if stderr != '':
            self.stderr_lines.extend(stderr.split('\n'))
        # tODO: include changed here?
        return exit_code, stdout, stderr


def main():
    module = AnsibleModule(argument_spec=dict(
        kubeconfig=dict(required=True, type='dict'),
        namespace=dict(required=True, type='str'),
        debug=dict(required=False, choices=BOOLEANS, default='false'),
        inline=dict(required=False, type='str'),
    ))

    # Validate module inputs:

    kubeconfig = module.params['kubeconfig']
    kubeconfig_file = None
    temp_kubeconfig_path = None
    if 'file' in kubeconfig and 'inline' in kubeconfig:
        pass # TODO: error here
    if 'file' in kubeconfig:
        # TODO: copy the kubeconfig for safety reasons.
        kubeconfig_file = kubeconfig['file']
    elif 'inline' in kubeconfig:
        tmpfile, temp_kubeconfig_path = tempfile.mkstemp()
        tmpfile = open(tmpfile, 'w')
        tmpfile.write(kubeconfig['inline'])
        tmpfile.close()
        kubeconfig_file = temp_kubeconfig_path

    applier = KubectlApplier(
            kubeconfig=kubeconfig_file,
            namespace=module.params['namespace'],
            inline=module.params['inline'],
            debug=module.boolean(module.params['debug']))
    exit_code, stdout, stderr = applier.run()

    # Cleanup:
    # TODO: wrap the above in try?
    if temp_kubeconfig_path:
        os.remove(temp_kubeconfig_path)

    module.exit_json(
            changed=applier.changed,
            debug=applier.debug_lines,
            exit_code=exit_code,
            stderr_lines=applier.stderr_lines,
            stdout_lines=applier.stdout_lines)


if __name__ == '__main__':
    main()
