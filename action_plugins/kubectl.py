from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import shutil
import tempfile

from ansible.plugins.action import ActionBase
from ansible.utils.vars import merge_hash


class ActionModule(ActionBase):

    TRANSFERS_FILES = True
    DEFAULT_NEWLINE_SEQUENCE = "\n"

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        action_mod_debug = []

        results = super(ActionModule, self).run(tmp, task_vars)
        #del results['invocation']['module_args']

        # Patch, edit, and transfer any files specified:
        files = task_vars.get('files', [])
        for filename in files:
            action_mod_debug.append('got filename: %s' % filename['src'])
            # TODO: secure copy
            copy_args = dict(
                src=filedef['src'],
                dest='/tmp/test1.yaml',
            )
            copy_results = self._execute_module(module_name=copy, module_args=copy_args,
                tmp=tmp, task_vars=task_vars)
            results['copy'] = copy_results

        # source = task_vars.get('src', None)
        # if source is None:
            # results['failed'] = True
            # results['msg'] = "src is required"

        if 'failed' in results:
            return results


        # Execute the kubectl module itself on remote host:
        results = merge_hash(results, self._execute_module(tmp=tmp, task_vars=task_vars))
        #results['debug'] = action_mod_debug.extend(results['debug'])

        return results

