# Kubectl Wrapper Modules For Ansible

The recommended approach for declarative management of Kubernetes config is
`kubectl apply`, which contains sophisticated logic for performing a three way
merge between an an objects incoming config, last applied config, and current
state.  This logic however is implemented client side, and thus not available
to callers of the API (including the current kubernetes module), and non-Go
languages. In the future this logic may move to the API, however this is not
expected near term.

However kubectl is intended to be treated as a type of API, as such in the
interim we can leverage it's logic by wrapping in Ansible modules.

This prototype is specific to generically managing actual Kubernetes config, it
does not wrap Kubernetes yaml in Ansible yaml, or expose individual modules per
individual Kubernetes type.

This prototype aims to make applying Kubernetes config via Ansible easy, and
consistent with the expected experience for config management in kubernetes.
(including on the fly templating, simple yaml edits, file based and inline
config, and patching) For more information see:

  * [Declarative Application Management In Kubernetes](https://docs.google.com/document/d/1cLPGweVEYrVqQvBLJg6sxV-TrE5Rm2MNOBA_cxZP2WU/edit?usp=sharing)

`kubectl delete` is represented by state: absent on the kubectl module itself.

`kubectl get` is represented by a kubectl_facts module.

## Assumptions

  * kubectl apply will be modified to accurately [report if changes had to be applied](https://github.com/kubernetes/kubernetes/pull/52647).

# Target Ansible

```yaml
- kubectl:

    # State present implies kubectl apply, and absent implies delete. Many options
    # below would not be relevant for delete.
    state: present

    kubeconfig:
      # Kubeconfig file on the remote host:
      file: /etc/origin/master/admin.kubeconfig
      # Alternatively:
      inline: "{{ lookup('file', 'local_on_control_host.kubeconfig') }}"

    # Optional, omit if your configuration specifies a namespace, or you're operating on
    # cluster level objects.
    namespace: default

    # You can specify your kubernetes config inline if desired. The | is important here:
    inline: |
      kind: "Namespace"
      apiVersion: v1
      metadata:
        name: testnamespace

    # Alternatively you can use files that live with your role/playbook. This would be
    # mutually exclusive with inline data.
    # Each file is copied over to the remote host, potentially edited or patched, and
    # then submitted with apply.
    # Specifying multiple files implies one execution of kubectl apply. If you want multiple
    # you can use separate tasks or a with_items loop.
    files:
    - src: configmap.json
    - src: subdir/
    - src: service.yml
      # Support small edits to the yaml on the fly, without going to a full template. Operates
      # on the temporary copy of the file sent to the remote host.
      # TODO: should yedit be embedded here? or somehow available as a separate module (while
      # still not requiring the user to pointless template out and write/read a file)
      yedit:
        key: spec.metadata.name
        value: "{{ replacement_name }}"
        value_type: list
    - src: patchme.yml
      # Support supplying structured patches with "kubectl patch" prior to submitting to the server.
      patches:
      - patch1.yml
      - patch2.yml
    # This would be nice too, kubectl supports, would likely imply no yediting or patching unless
    # we want the module to be in the business of fetching files.
    - src: https://github.com/me/project/template.yml

    # Support templating files out automatically. Use Ansible's native mechanisms for jinja
    # templates but don't require the user to copy the file and manually clean it up with
    # their own tasks.
    templates:
    - src: apptemplate.yml
      vars:
        foo: bar

    # Control what binary to use, as oc is required for apply operations on OpenShift types:
    binary: oc

    # Various other kubectl options could be supported:
    prune: true
    dry_run: true
    overwrite: true
    selector: something=true


# kubectl delete is exposed as state absent:
- kubectl:
    kubeconfig:
      file: /etc/origin/master/admin.kubeconfig
    state: absent
    files:
    - src: subdir/
    - src: configmap.json
    inline: |
      kind: "Namespace"
      apiVersion: v1
      metadata:
        name: testnamespace


- kubectl_facts:
    kubeconfig:
      file: /etc/origin/master/admin.kubeconfig
    namespace: openshift
    kind: configmap
    output: json(default)|yaml|TBD
    selector: app=X
  register: openshift_configmaps
```
