#!/usr/bin/env python3
"""
Node initializer for VESSL-managed clusters.
This script is expected to run as a DaemonSet.
It patches containerd config to use a mirror for Quay.
"""

import datetime
import os
import subprocess

import tomli
import tomli_w

HOST_PATH = '/host'
CONTAINERD_CONFIG_PATH = os.environ.get('CONTAINERD_CONFIG_PATH', '').strip() or '/etc/containerd/config.toml'
OVERRIDE_MAGIC = '__VESSL_OVERRIDDEN__'
CONTAINERD_REGISTRY_BASE_PATH = os.environ.get('CONTAINERD_REGISTRY_BASE_PATH', '').strip() or '/etc/containerd/vessl_hosts'
QUAY_MIRROR_URL_ENVVAR_NAME = 'QUAY_MIRROR_URL'
SHOULD_ADD_GCR_MIRROR_ENVVAR_NAME = 'SHOULD_ADD_GCR_MIRROR'
RESTART_CONTAINERD_ENVVAR_NAME = 'RESTART_CONTAINERD'

class NodeInitError(Exception):
    pass

def _log(message: str):
    time_str = datetime.datetime.now().isoformat()
    print(f'{time_str}: {message}')

def _hosts_toml_quay_io():
    quay_mirror_url = os.environ.get(QUAY_MIRROR_URL_ENVVAR_NAME, '').strip()
    if quay_mirror_url == "":
        raise NodeInitError(
            f"Cannot find Quay mirror URL: envvar {QUAY_MIRROR_URL_ENVVAR_NAME} is empty"
        )

    if not quay_mirror_url.startswith('http://') and not quay_mirror_url.startswith('https://'):
        quay_mirror_url = 'http://' + quay_mirror_url

    _log(f"Using Quay mirror URL: {quay_mirror_url}")

    return (
f"""
server = "https://quay.io"
[host."{quay_mirror_url}"]
  capabilities = ["pull", "resolve"]
  override_path = true
"""
    ).lstrip()

def _hosts_toml_docker_io():
    should_add_gcr_mirror_str = os.environ.get(SHOULD_ADD_GCR_MIRROR_ENVVAR_NAME, '').strip()
    should_add_gcr_mirror = should_add_gcr_mirror_str.lower() in ['1', 'true', 'yes']

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
        return (
"""
server = "https://docker.io"

[host."https://registry-1.docker.io"]
  capabilities = ["pull", "resolve"]
"""
        ).lstrip()

def _build_containerd_registry_directory():
    base_path = HOST_PATH+CONTAINERD_REGISTRY_BASE_PATH

    os.makedirs(base_path, exist_ok=True)
    open(base_path + "/__README__.txt", 'w').write(
"""
This directory (and its contents) is created by cloud node initialization script from VESSL.
These files are parsed by containerd, which then refer to right services when pulling images.
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

    _write_file_with_log(base_path + "/quay.io", "hosts.toml", _hosts_toml_quay_io())
    _write_file_with_log(base_path + "/docker.io", "hosts.toml", _hosts_toml_docker_io())

    _log(f"Successfully created host directory at: {base_path}")

def _patch_containerd_config():
    config_path = HOST_PATH + CONTAINERD_CONFIG_PATH
    config_content_raw = open(config_path, encoding='utf-8').read()
    if OVERRIDE_MAGIC in config_content_raw:
        _log(f"Found magic string ({OVERRIDE_MAGIC}) in containerd config; "+
             "assuming already patched, will not touch it.")
        _log(f"NOTE: current containerd config:\n{config_content_raw}")
        return

    config = tomli.loads(config_content_raw)
    version = config.get('version', None)
    if version is None or version not in [2, 3]:
        _log(f"Could not find valid version from containerd config file ({CONTAINERD_CONFIG_PATH}).")
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
        registry_entry['config_path'] = f"{old_path}:{CONTAINERD_REGISTRY_BASE_PATH}"
    else:
        registry_entry['config_path'] = CONTAINERD_REGISTRY_BASE_PATH

    new_config_content_raw = tomli_w.dumps(config)
    new_config_content_raw += f"\n\n# {OVERRIDE_MAGIC}\n"
    open(config_path, 'w').write(new_config_content_raw)
    _log("Successfully updated containerd config.")
    _log(f"NOTE: new config:\n{new_config_content_raw}")

def _restart_containerd():
    _log("Restarting containerd...")
    subprocess.run(
        ["chroot", "/host", "systemctl", "restart", "containerd.service"]
    ).check_returncode()
    _log("Restarted containerd. Checking status...")
    subprocess.run(
        ["chroot", "/host", "systemctl", "status", "containerd.service"]
    ).check_returncode()
    _log("Successfully restarted containerd.")

def main():
    print('Phew! We made it.')

    if not os.path.isdir(HOST_PATH):
        raise NodeInitError(
            f"{HOST_PATH} is not a directory; cannot proceed. "+
            "(Did you forget to mount host path?)"
        )

    if not os.path.exists(HOST_PATH + CONTAINERD_CONFIG_PATH):
        raise NodeInitError(
            f"{HOST_PATH + CONTAINERD_CONFIG_PATH} does not exist; cannot proceed."
        )

    _build_containerd_registry_directory()
    _patch_containerd_config()

    if os.environ.get(RESTART_CONTAINERD_ENVVAR_NAME, '').lower().strip() in ['1', 'yes', 'true']:
        _restart_containerd()
    else:
        _log("Will not restart containerd (because config says so); please do that manually.")

if __name__ == "__main__":
    main()
