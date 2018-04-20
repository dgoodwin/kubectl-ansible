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
    def __init__(self, kubeconfig=None, namespace=None, inline=None, files=None, debug=None):
        self.kubeconfig = kubeconfig
        self.namespace = namespace
        self.inline = inline

        # Loads as a dict, convert to a json string for piping to kubectl:
        #self.inline = json.dumps(inline)
        self.files = files
        if self.files is None:
            self.files = []

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
        if self.inline:
            self.cmds.extend(["-f", "-"])
            self.debug_lines.append('Using inline input: %s' % self.inline)
            exit_code, stdout, stderr = self.cmd_runner.run(self.cmds, self.inline)
            self._process_cmd_result(exit_code, stdout, stderr)
            if self.failed:
                return

        # TODO: validate file dict
        for f in self.files:
            self.debug_lines.append("Processing file: %s" % f['src'])
            #self.cmds.extend(['-f', f['src']])
            self.cmds.extend(['-f', '/tmp/test1.yaml'])
            # No stdin input requires when applying a file/dir:
            exit_code, stdout, stderr = self.cmd_runner.run(self.cmds, None)
            self._process_cmd_result(exit_code, stdout, stderr)
            if self.failed:
                return

    def _process_cmd_result(self, exit_code, stdout, stderr):
        if stdout != '':
            self.stdout_lines.extend(stdout.split('\n'))
        if stderr != '':
            self.stderr_lines.extend(stderr.split('\n'))
        self.changed = self.changed or (exit_code == 0)
        self.failed = self.failed or (exit_code > 0 and exit_code != 3)


def main():
    module = AnsibleModule(argument_spec=dict(
        kubeconfig=dict(required=True, type='dict'),
        namespace=dict(required=True, type='str'),
        debug=dict(required=False, type='bool', default='false'),
        inline=dict(required=False, type='str'),
        files=dict(required=False, type='list'),
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
        #tmpfile = open(tmpfile, 'w')
        with open(temp_kubeconfig_path, 'w') as f:
            f.write(kubeconfig['inline'])
        os.close(fd)
        kubeconfig_file = temp_kubeconfig_path

    applier = KubectlApplier(
            kubeconfig=kubeconfig_file,
            namespace=module.params['namespace'],
            inline=module.params['inline'],
            files=module.params['files'],
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
