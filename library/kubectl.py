import os
import json
import subprocess
import tempfile
import yaml

from ansible.module_utils.basic import AnsibleModule

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

        encoded_input = input_data.encode() if input_data else None
        # TODO: encode here was required on Python 3, watchout for 2:
        stdout, stderr = proc.communicate(encoded_input)
        return proc.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')


class KubectlApplier(object):
    def __init__(self, kubeconfig=None, namespace=None, definition=None, src=None, debug=None):
        self.kubeconfig = kubeconfig
        self.namespace = namespace
        self.definition = definition

        # Loads as a dict, convert to a json string for piping to kubectl:
        #self.definition = json.dumps(definition)
        self.src = src

        self.cmds = ["kubectl", "apply"]

        if self.namespace:
            self.cmds.extend(["-n", self.namespace])
        self.cmd_runner = KubectlRunner(self.kubeconfig)

        self.changed = False
        self.failed = False
        self.debug_lines = []
        self.stdout_lines = []
        self.stderr_lines = []

    def run(self):
        exit_code, stdout, stderr = (None, None, None)
        if self.definition:
            self.cmds.extend(["-f", "-"])
            # We end up with a string here containing json, but using single quotes instead of double,
            # which does not parse as valid json. Replace them instead so kubectl is happy:
            # TODO: is this right?
            self.definition = self.definition.replace('\'', '"')
            self.debug_lines.append('Using definition input: %s' % self.definition)
            self.debug_lines.append('Using definition type: %s' % type(self.definition))
            exit_code, stdout, stderr = self.cmd_runner.run(self.cmds, self.definition)
            self._process_cmd_result(exit_code, stdout, stderr)
            if self.failed:
                return
        elif self.src:
            self.debug_lines.append('src: %s' % self.src)
            self.cmds.extend(["-f", self.src])
            # path = os.path.normpath(src)
            # if not os.path.exists(path):
                # self.fail_json(msg="Error accessing {0}. Does the file exist?".format(path))
            exit_code, stdout, stderr = self.cmd_runner.run(self.cmds, None)
            self._process_cmd_result(exit_code, stdout, stderr)

    def _process_cmd_result(self, exit_code, stdout, stderr):
        if stdout != '':
            self.stdout_lines.extend(stdout.split('\n'))
        if stderr != '':
            self.stderr_lines.extend(stderr.split('\n'))
        self.changed = self.changed or (exit_code == 0)
        # This check for exit code 3 was from a kubernetes PR where this indicated
        # no changes needed to be applied. PR however did not merge and was clused
        # when the server-side apply effort began.
        self.failed = self.failed or (exit_code > 0 and exit_code != 3)


def main():
    module = AnsibleModule(argument_spec=dict(
        kubeconfig=dict(required=True, type='dict'),
        namespace=dict(required=True, type='str'),
        debug=dict(required=False, type='bool', default='false'),
        definition=dict(required=False, type='str'),
        src=dict(required=False, type='str'),
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
        fd, temp_kubeconfig_path = tempfile.mkstemp()
        with open(temp_kubeconfig_path, 'w') as f:
            f.write(kubeconfig['inline'])
        os.close(fd)
        kubeconfig_file = temp_kubeconfig_path

    applier = KubectlApplier(
        kubeconfig=kubeconfig_file,
        namespace=module.params['namespace'],
        definition=module.params['definition'],
        src=module.params['src'],
        debug=module.boolean(module.params['debug']))
    applier.run()

    # Cleanup:
    # TODO: wrap the above in try?
    if temp_kubeconfig_path:
        os.remove(temp_kubeconfig_path)

    if applier.failed:
        module.fail_json(
            msg="error executing kubectl apply",
            debug=applier.debug_lines,
            stderr_lines=applier.stderr_lines,
            stdout_lines=applier.stdout_lines)
    else:
        module.exit_json(
            changed=applier.changed,
            debug=applier.debug_lines,
            stderr_lines=applier.stderr_lines,
            stdout_lines=applier.stdout_lines)


if __name__ == '__main__':
    main()
