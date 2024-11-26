#!/usr/bin/env python3
"""
Node initializer for VESSL-managed clusters.
This script is expected to run as a DaemonSet.
It patches containerd config to use a mirror for Quay.
"""

import datetime
import os
import subprocess
import typing
from typing import List

import tomli
import tomli_w
from kubernetes import client, config
from kubernetes.client.models import V1NodeList, V1Node, V1NodeSpec, V1Taint

HOST_PATH = '/host'
OVERRIDE_MAGIC = '__VESSL_OVERRIDDEN__'
NODE_TAINT_NAME = 'startup-taint.cluster-autoscaler.kubernetes.io/registry-cache'
QUAY_MIRROR_URL_ENVVAR_NAME = 'QUAY_MIRROR_URL'
SHOULD_ADD_GCR_MIRROR_ENVVAR_NAME = 'SHOULD_ADD_GCR_MIRROR'
SHOULD_REMOVE_NODE_TAINT_ENVVAR_NAME = 'SHOULD_REMOVE_NODE_TAINT'
NODE_NAME_ENVVAR_NAME = 'NODE_NAME'
CONTAINERD = {
    'NAME': 'containerd',
    'CONFIG_PATH': os.environ.get('CONTAINERD_CONFIG_PATH', '').strip() or '/etc/containerd/config.toml',
    'REGISTRY_BASE_PATH': os.environ.get('CONTAINERD_REGISTRY_BASE_PATH', '').strip() or '/etc/containerd/vessl_hosts',
    'RESTART_ENVVAR_NAME': 'RESTART_CONTAINERD'
}
CRI_O = {
    'NAME': 'crio',
    'CONFIG_PATH': '/etc/containers/registries.conf',
    'REGISTRY_BASE_PATH': '/etc/containers/registries.conf.d',
    'RESTART_ENVVAR_NAME': 'RESTART_CRIO'
}
SUPPORTED_RUNTIMES = [CONTAINERD, CRI_O]


class NodeInitError(Exception):
    pass


def _log(message: str):
    time_str = datetime.datetime.now().isoformat()
    print(f'{time_str}: {message}')


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in ['1', 'true', 'yes', 'y']


def _hosts_toml_quay_io(runtime: str) -> str:
    quay_mirror_url = os.environ.get(QUAY_MIRROR_URL_ENVVAR_NAME, '').strip()
    if not quay_mirror_url:
        raise NodeInitError(f"Cannot find Quay mirror URL: envvar {QUAY_MIRROR_URL_ENVVAR_NAME} is empty")

    _log(f"Using Quay mirror URL: {quay_mirror_url}")

    if runtime == CONTAINERD['NAME']:
        if not quay_mirror_url.startswith(('http://', 'https://')):
            quay_mirror_url = 'http://' + quay_mirror_url

        return (
    f"""
    server = "https://quay.io"
    [host."{quay_mirror_url}"]
      capabilities = ["pull", "resolve"]
      override_path = true
    """
        ).lstrip()
    elif runtime == CRI_O['NAME']:
        return (
    f"""
[[registry]]
prefix = "quay.io"
insecure = false
blocked = false
location = "quay.io"
[[registry.mirror]]
insecure = true
location = "{quay_mirror_url}"
"""
        ).lstrip()

def _hosts_toml_docker_io(runtime: str) -> str:
    should_add_gcr_mirror = _is_truthy(os.environ.get(SHOULD_ADD_GCR_MIRROR_ENVVAR_NAME, ''))

    _log(f"Should add GCR mirror to docker.io?... {should_add_gcr_mirror}")

    if should_add_gcr_mirror:
        return (
"""
server = "https://docker.io"

[host."https://mirror.gcr.io"]
  capabilities = ["pull", "resolve"]
[host."https://registry-1.docker.io"]
  capabilities = ["pull", "resolve"]
"""
        ).lstrip()
    else:
        if runtime == CONTAINERD['NAME']:
            return (
    """
    server = "https://docker.io"

    [host."https://registry-1.docker.io"]
      capabilities = ["pull", "resolve"]
    """
            ).lstrip()

def _build_registry_directory(runtime: dict):
    base_path = HOST_PATH + runtime['REGISTRY_BASE_PATH']

    os.makedirs(base_path, exist_ok=True)
    open(base_path + "/__README__.txt", 'w').write(
f"""
This directory (and its contents) is created by cloud node initialization script from VESSL.
These files are parsed by {runtime['NAME']}, which then refer to right services when pulling images.
""".lstrip()
    )

    def _write_file_with_log(directory: str, basename: str, content: str):
        os.makedirs(directory, exist_ok=True)

        full_path = os.path.join(directory, basename)
        if os.path.isfile(full_path):
            _log(f"File {full_path} already exists. Will overwrite.")

        open(full_path, 'w').write(content)
        _log(f"Successfully wrote {full_path}.")
        _log(f"NOTE: content:\n{content}")

    if runtime['NAME'] == CONTAINERD['NAME']:
        _write_file_with_log(base_path + "/quay.io", "hosts.toml", _hosts_toml_quay_io(runtime['NAME']))  # basename 보기
        _write_file_with_log(base_path + "/docker.io", "hosts.toml", _hosts_toml_docker_io(runtime['NAME']))
    elif runtime['NAME'] == CRI_O['NAME']:
        _write_file_with_log(base_path, "quay.conf", _hosts_toml_quay_io(runtime['NAME']))

    _log(f"Successfully created host directory at: {base_path}")

def _patch_containerd_config():
    config_path = HOST_PATH + CONTAINERD['CONFIG_PATH']
    config_content_raw = open(config_path, encoding='utf-8').read()
    if OVERRIDE_MAGIC in config_content_raw:
        _log(f"Found magic string ({OVERRIDE_MAGIC}) in containerd config; " +
             "assuming already patched, will not touch it.")
        _log(f"NOTE: current containerd config:\n{config_content_raw}")
        return

    config = tomli.loads(config_content_raw)
    version = config.get('version', None)
    if version is None or version not in [2, 3]:
        _log(f"Could not find valid version from containerd config file ({CONTAINERD['CONFIG_PATH']}).")
        _log("Specifically, I expected either version 2 or 3, but got: {version}.")
        _log("The containerd config file is either damaged, or has a format that I don't understand.")
        _log("Aborting to avoid possible damages.")
        _log(f"NOTE: current containerd config:\n{config_content_raw}")
        raise NodeInitError("Containerd config file format not recognized")

    is_containerd_1_x = version == 2
    plugin_name = 'io.containerd.grpc.v1.cri' if is_containerd_1_x else 'io.containerd.cri.v1.images'

    def _ensure_key(toml_obj, path):
        while path:
            key = path[0]
            if key not in toml_obj:
                toml_obj[key] = {}
            toml_obj = toml_obj[key]
            path = path[1:]
    _ensure_key(config, ['plugins', plugin_name, 'registry'])
    registry_entry = config['plugins'][plugin_name]['registry']

    if 'mirrors' in registry_entry:
        del registry_entry['mirrors']

    if 'config_path' in registry_entry:
        old_path = registry_entry['config_path']
        _log(f"Containerd config already has config_path: {old_path}")
        _log("Appending our config dir to it.")
        registry_entry['config_path'] = f"{old_path}:{CONTAINERD['REGISTRY_BASE_PATH']}"
    else:
        registry_entry['config_path'] = CONTAINERD['REGISTRY_BASE_PATH']

    new_config_content_raw = tomli_w.dumps(config)
    new_config_content_raw += f"\n\n# {OVERRIDE_MAGIC}\n"
    open(config_path, 'w').write(new_config_content_raw)
    _log("Successfully updated containerd config.")
    _log(f"NOTE: new config:\n{new_config_content_raw}")

def _restart_runtime(runtime_name: str):
    _log(f"Restarting {runtime_name}...")
    subprocess.run(
        ["chroot", "/host", "systemctl", "restart", f"{runtime_name}.service"]
    ).check_returncode()
    _log(f"Restarted {runtime_name}. Checking status...")
    subprocess.run(
        ["chroot", "/host", "systemctl", "status", f"{runtime_name}.service"]
    ).check_returncode()
    _log(f"Successfully restarted {runtime_name}.")

def _remove_node_taint():
    should_remove_taint = _is_truthy(os.environ.get(SHOULD_REMOVE_NODE_TAINT_ENVVAR_NAME, ''))
    if not should_remove_taint:
        _log("Not indicated to remove node taint, so will not remove taint.")
        return

    node_name = os.environ.get(NODE_NAME_ENVVAR_NAME, "").strip()
    if not node_name:
        _log(f"Cannot find node name (in envvar {NODE_NAME_ENVVAR_NAME})!")
        _log("Will not remove node taint.")
        return

    config.load_incluster_config()
    v1 = client.CoreV1Api()

    _log(f"Trying to read node {node_name}...")
    node: V1Node = v1.read_node(name=node_name) # type: ignore
    _log(f"Successfully read node {node_name} from Kubernetes API.")

    spec: V1NodeSpec = node.spec # type: ignore
    taints: List[V1Taint] = spec.taints or [] # type: ignore

    for i, taint in enumerate(taints):
        key: str = taint.key # type: ignore
        if key == NODE_TAINT_NAME:
            break
    else:
        # prepare pretty message
        keys: List[str] = [taint.key for taint in taints] # type: ignore
        _log(f"No matching taint found on node {node_name}.")
        _log(f"Expected: {NODE_TAINT_NAME}, saw: {', '.join(keys)}")
        return

    _log(f"Found taint: {taint}")
    new_taints = taints[:i] + taints[i+1:]
    _log("Trying to patch node to not have this taint...")
    v1.patch_node(node_name, { "spec": { "taints": new_taints } })
    _log("Done.")

def _find_container_runtime() -> dict:
    if os.path.exists(HOST_PATH + CONTAINERD['CONFIG_PATH']):
        return CONTAINERD
    elif os.path.exists(HOST_PATH + CRI_O['CONFIG_PATH']):
        return CRI_O
    else:
        raise NodeInitError(
            f"Cannot find container runtime config file (please check if {' or '.join([runtime['NAME'] for runtime in SUPPORTED_RUNTIMES])} is installed)")

def main():
    print('Phew! We made it.')

    if not os.path.isdir(HOST_PATH):
        raise NodeInitError(
            f"{HOST_PATH} is not a directory; cannot proceed. "+
            "(Did you forget to mount host path?)"
        )

    runtime = _find_container_runtime()
    _build_registry_directory(runtime)

    if runtime['NAME'] == CONTAINERD['NAME']:
        _patch_containerd_config()
        if os.environ.get(CONTAINERD['RESTART_ENVVAR_NAME'], '').lower().strip() in ['1', 'yes', 'true']:
            _restart_runtime(runtime['NAME'])
        else:
            _log("Will not restart containerd (because config says so); please do that manually.")
    elif runtime['NAME'] == CRI_O['NAME']:
        if os.environ.get(CRI_O['RESTART_ENVVAR_NAME'], '').lower().strip() in ['1', 'yes', 'true']:
            _restart_runtime(runtime['NAME'])
        else:
            _log("Will not restart cri-o (because config says so); please do that manually.")

    _remove_node_taint()


if __name__ == "__main__":
    main()