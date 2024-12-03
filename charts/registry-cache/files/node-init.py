#!/usr/bin/env python3
"""
Node initializer for VESSL-managed clusters.
This script is expected to run as a DaemonSet.
It patches containerd config to use a mirror for Quay.
"""

import datetime
import os
import subprocess
from typing import List, Type

import tomli
import tomli_w
from kubernetes import client, config
from kubernetes.client.models import V1Node, V1NodeSpec, V1Taint

HOST_PATH = "/host"
OVERRIDE_MAGIC = "__VESSL_OVERRIDDEN__"
NODE_TAINT_NAME = "startup-taint.cluster-autoscaler.kubernetes.io/registry-cache"
QUAY_MIRROR_URL_ENVVAR_NAME = "QUAY_MIRROR_URL"
SHOULD_ADD_GCR_MIRROR_ENVVAR_NAME = "SHOULD_ADD_GCR_MIRROR"
SHOULD_REMOVE_NODE_TAINT_ENVVAR_NAME = "SHOULD_REMOVE_NODE_TAINT"
NODE_NAME_ENVVAR_NAME = "NODE_NAME"


class NodeInitError(Exception):
    pass


def _log(message: str):
    time_str = datetime.datetime.now().isoformat()
    print(f"{time_str}: {message}")


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in ["1", "true", "yes", "y"]


def _get_quay_mirror_url() -> str:
    quay_mirror_url = os.environ.get(QUAY_MIRROR_URL_ENVVAR_NAME, "").strip()
    if not quay_mirror_url:
        raise NodeInitError(
            f"Cannot find Quay mirror URL: envvar {QUAY_MIRROR_URL_ENVVAR_NAME} is empty"
        )

    return quay_mirror_url


def _get_should_add_gcr_mirror() -> bool:
    return _is_truthy(os.environ.get(SHOULD_ADD_GCR_MIRROR_ENVVAR_NAME, ""))


def _write_file_with_log(directory: str, basename: str, content: str):
    os.makedirs(directory, exist_ok=True)

    full_path = os.path.join(directory, basename)
    if os.path.isfile(full_path):
        _log(f"File {full_path} already exists. Will overwrite.")

    open(full_path, "w").write(content)
    _log(f"Successfully wrote {full_path}.")
    _log(f"NOTE: content:\n{content}")


def _remove_node_taint():
    should_remove_taint = _is_truthy(os.environ.get(SHOULD_REMOVE_NODE_TAINT_ENVVAR_NAME, ""))
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
    node: V1Node = v1.read_node(name=node_name)  # type: ignore
    _log(f"Successfully read node {node_name} from Kubernetes API.")

    spec: V1NodeSpec = node.spec  # type: ignore
    taints: List[V1Taint] = spec.taints or []  # type: ignore

    for i, taint in enumerate(taints):
        key: str = taint.key  # type: ignore
        if key == NODE_TAINT_NAME:
            break
    else:
        # prepare pretty message
        keys: List[str] = [taint.key for taint in taints]  # type: ignore
        _log(f"No matching taint found on node {node_name}.")
        _log(f"Expected: {NODE_TAINT_NAME}, saw: {', '.join(keys)}")
        return

    _log(f"Found taint: {taint}")
    new_taints = taints[:i] + taints[i + 1 :]
    _log("Trying to patch node to not have this taint...")
    v1.patch_node(node_name, {"spec": {"taints": new_taints}})
    _log("Done.")


class AbstractRuntime:
    name: str

    @classmethod
    def is_runtime_found(cls) -> bool:
        raise NotImplementedError()

    @classmethod
    def initialize_node(cls) -> None:
        raise NotImplementedError()


class Containerd(AbstractRuntime):
    name: str = "containerd"
    restart_env_var_name: str = "RESTART_CONTAINERD"

    @classmethod
    def _get_config_path(cls) -> str:
        return os.environ.get("CONTAINERD_CONFIG_PATH", "").strip() or "/etc/containerd/config.toml"

    @classmethod
    def _get_registry_base_path(cls) -> str:
        return (
            os.environ.get("CONTAINERD_REGISTRY_BASE_PATH", "").strip()
            or "/etc/containerd/vessl_hosts"
        )

    @classmethod
    def is_runtime_found(cls) -> bool:
        return os.path.exists(HOST_PATH + cls._get_config_path())

    @classmethod
    def initialize_node(cls) -> None:
        cls._build_registry_directory()
        cls._patch_containerd_config()

        if _is_truthy(os.environ.get(cls.restart_env_var_name, "")):
            cls._restart_containerd()
        else:
            _log("Will not restart containerd (because config says so); please do that manually.")

    @classmethod
    def _build_registry_directory(cls) -> None:
        base_path = HOST_PATH + cls._get_registry_base_path()

        os.makedirs(base_path, exist_ok=True)
        open(base_path + "/__README__.txt", "w").write(
            """
This directory (and its contents) is created by cloud node initialization script from VESSL.
These files are parsed by containerd, which then refer to right services when pulling images.
""".lstrip()
        )

        quay_toml = cls._get_quay_toml()
        docker_toml = cls._get_docker_toml()

        _write_file_with_log(base_path + "/quay.io", "hosts.toml", quay_toml)
        _write_file_with_log(base_path + "/docker.io", "hosts.toml", docker_toml)

        _log(f"Successfully created host directory at: {base_path}")

    @classmethod
    def _get_quay_toml(cls) -> str:
        quay_mirror_url = _get_quay_mirror_url()
        _log(f"Using Quay mirror URL: {quay_mirror_url}")

        if not quay_mirror_url.startswith(("http://", "https://")):
            quay_mirror_url = "http://" + quay_mirror_url

        return (
            f"""
    server = "https://quay.io"
    [host."{quay_mirror_url}"]
      capabilities = ["pull", "resolve"]
      override_path = true
    """
        ).lstrip()

    @classmethod
    def _get_docker_toml(cls) -> str:
        should_add_gcr_mirror = _get_should_add_gcr_mirror()
        _log(f"Should add GCR mirror to docker.io?... {should_add_gcr_mirror}")

        if should_add_gcr_mirror:
            return """
server = "https://docker.io"

[host."https://mirror.gcr.io"]
    capabilities = ["pull", "resolve"]

[host."https://registry-1.docker.io"]
    capabilities = ["pull", "resolve"]
""".lstrip()
        else:
            return """
server = "https://docker.io"

[host."https://registry-1.docker.io"]
    capabilities = ["pull", "resolve"]
"""

    @classmethod
    def _patch_containerd_config(cls) -> None:
        config_content_raw = open(HOST_PATH + cls._get_config_path(), encoding="utf-8").read()
        if OVERRIDE_MAGIC in config_content_raw:
            _log(
                f"Found magic string ({OVERRIDE_MAGIC}) in containerd config; "
                + "assuming already patched, will not touch it."
            )
            _log(f"NOTE: current containerd config:\n{config_content_raw}")
            return

        config = tomli.loads(config_content_raw)
        version = config.get("version", None)
        if version is None or version not in [2, 3]:
            _log(
                f"Could not find valid version from containerd config file ({cls._get_config_path()})."
            )
            _log("Specifically, I expected either version 2 or 3, but got: {version}.")
            _log(
                "The containerd config file is either damaged, or has a format that I don't understand."
            )
            _log("Aborting to avoid possible damages.")
            _log(f"NOTE: current containerd config:\n{config_content_raw}")
            raise NodeInitError("Containerd config file format not recognized")

        is_containerd_1_x = version == 2
        plugin_name = (
            "io.containerd.grpc.v1.cri" if is_containerd_1_x else "io.containerd.cri.v1.images"
        )

        def _ensure_key(toml_obj, path):
            while path:
                key = path[0]
                if key not in toml_obj:
                    toml_obj[key] = {}
                toml_obj = toml_obj[key]
                path = path[1:]

        _ensure_key(config, ["plugins", plugin_name, "registry"])
        registry_entry = config["plugins"][plugin_name]["registry"]

        if "mirrors" in registry_entry:
            del registry_entry["mirrors"]

        if "config_path" in registry_entry:
            old_path = registry_entry["config_path"]
            _log(f"Containerd config already has config_path: {old_path}")
            _log("Appending our config dir to it.")
            registry_entry["config_path"] = f"{old_path}:{cls._get_registry_base_path()}"
        else:
            registry_entry["config_path"] = cls._get_registry_base_path()

        new_config_content_raw = tomli_w.dumps(config)
        new_config_content_raw += f"\n\n# {OVERRIDE_MAGIC}\n"
        open(HOST_PATH + cls._get_config_path(), "w").write(new_config_content_raw)
        _log("Successfully updated containerd config.")
        _log(f"NOTE: new config:\n{new_config_content_raw}")

    @classmethod
    def _restart_containerd(cls) -> None:
        _log("Restarting containerd...")
        subprocess.run(
            ["chroot", "/host", "systemctl", "restart", "containerd.service"]
        ).check_returncode()
        _log("Restarted containerd. Checking status...")
        subprocess.run(
            ["chroot", "/host", "systemctl", "status", "containerd.service"]
        ).check_returncode()
        _log("Successfully restarted containerd.")


class Crio(AbstractRuntime):
    name: str = "crio"
    restart_env_var_name: str = "RESTART_CRIO"

    @classmethod
    def _get_registry_base_path(cls) -> str:
        return "/etc/containers/registries.conf.d"

    @classmethod
    def is_runtime_found(cls) -> bool:
        config_path = (
            os.environ.get("CRIO_CONFIG_PATH", "").strip() or "/etc/containers/registries.conf"
        )
        return os.path.exists(HOST_PATH + config_path)

    @classmethod
    def initialize_node(cls) -> None:
        cls._build_registry_directory()

        if _is_truthy(os.environ.get(cls.restart_env_var_name, "")):
            cls._reload_crio()
        else:
            _log("Will not restart CRI-O (because config says so); please do that manually.")

    @classmethod
    def _build_registry_directory(cls) -> None:
        base_path = HOST_PATH + cls._get_registry_base_path()

        os.makedirs(base_path, exist_ok=True)
        open(base_path + "/__README__.txt", "w").write(
            """
This directory (and its contents) is created by cloud node initialization script from VESSL.
These files are parsed by CRI-O, which then refer to right services when pulling images.
""".lstrip()
        )

        quay_toml = cls._get_quay_toml()
        _write_file_with_log(base_path, "quay.conf", quay_toml)

        _log(f"Successfully created host directory at: {base_path}")

    @classmethod
    def _get_quay_toml(cls) -> str:
        quay_mirror_url = _get_quay_mirror_url()
        for forbidden_prefix in ["http://", "https://"]:
            if quay_mirror_url.startswith(forbidden_prefix):
                quay_mirror_url = quay_mirror_url[len(forbidden_prefix) :]
        _log(f"Using Quay mirror URL: {quay_mirror_url}")

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

    @classmethod
    def _reload_crio(cls) -> None:
        _log("Reloading CRI-O...")
        subprocess.run(
            ["chroot", "/host", "systemctl", "reload", "cri-o.service"]
        ).check_returncode()
        _log("Restarted CRI-O. Checking status...")
        subprocess.run(
            ["chroot", "/host", "systemctl", "status", "cri-o.service"]
        ).check_returncode()
        _log("Successfully restarted CRI-O.")


supported_runtimes: dict[str, Type[AbstractRuntime]] = {
    "containerd": Containerd,
    "crio": Crio,
}


def _find_container_runtime() -> Type[AbstractRuntime]:
    for runtime in supported_runtimes.values():
        if runtime.is_runtime_found():
            return runtime
    else:
        raise NodeInitError(
            f"Cannot find container runtime config file! Supported runtimes: {', '.join(supported_runtimes)}"
        )


def main():
    print("Phew! We made it.")

    if not os.path.isdir(HOST_PATH):
        raise NodeInitError(
            f"{HOST_PATH} is not a directory; cannot proceed. "
            + "(Did you forget to mount host path?)"
        )

    runtime = _find_container_runtime()
    runtime.initialize_node()

    _remove_node_taint()


if __name__ == "__main__":
    main()
