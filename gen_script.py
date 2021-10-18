import yaml
import io
import argparse
from pathlib import Path

# commands
_ip = "/usr/sbin/ip"
_bash = "/bin/bash"
_podman = "/usr/bin/podman"
# useful vars
_discard = " 2> /dev/null"


class Unit:

    def __init__(self, cfg: dict):
        self._buffer = io.StringIO()
        self._write = lambda s="": self._buffer.write(s + '\n')
        self._comment = lambda s="": self._buffer.write('# ' + s + '\n')
        self._cfg = cfg
        self._load_nic()

    def _load_nic(self):
        # convention: v1 in netns, v2 in host
        for nic in self._cfg['nics_list']:
            if nic['type'] == 'bridge':
                nic_name = nic['nic'].replace('-', '').replace('_', '')
                nic['veth_prefix'] = "veth" + nic_name[:6]

    def _script_head(self):
        self._write("#!/bin/bash")
        self._write("set -xe")
        self._write("\n# auto generated unit files, DO NOT EDIT!\n")

    def _cleanup_netns(self):
        self._comment("cleanup netns")
        for nic in self._cfg['nics_list']:
            if nic['type'] == 'bridge':
                self._comment(f"cleanup veth pair: {nic['veth_prefix']}")
                self._write(f"!{_ip} link set {nic['veth_prefix']}2 down")
                self._write(f"!{_ip} link del {nic['veth_prefix']}2")
            elif nic['type'] == 'interface':
                self._comment(f"release imported interface: {nic['nic']}")
                self._write(f"{_ip} netns exec ip link set {nic['nic']} down")
                self._write(f"{_ip} netns exec ip link set {nic['nic']} netns 1")
        self._comment("delete old netns")
        self._write(f"! {_ip} netns del {self._cfg['netns']}")


    def _cleanup_container(self):
        self._comment("cleanup old container")
        self._write(f"! {_podman} rm -f {self._cfg['container_name']} {_discard}")

    def _cleanup_cidpid(self):
        self._comment("delete old cid pid files")
        self._write(f"! rm -f /run/{self._cfg['container_name']}.cid {_discard}")
        self._write(f"! rm -f /run/{self._cfg['container_name']}.pid {_discard}")
        self._write()


class UnitRun(Unit):
    _caps = ["NET_ADMIN", "NET_RAW", "NET_BIND_SERVICE"]
    _entry = ["/sbin/init"]

    def __init__(self, cfg):
        super().__init__(cfg)

    def create_unit_file(self):
        self._script_head()
        self._clean_up()
        self._setup()
        return self._buffer.getvalue()

    def _clean_up(self):
        self._comment("remove previously created resources if any")
        self._cleanup_cidpid()
        self._cleanup_netns()
        self._cleanup_container()
        self._write()

    def _setup(self):
        self._comment("setup container")
        self._setup_netns()
        self._setup_run()

    def _setup_netns(self):
        self._comment("set up net namespace")
        self._write(f"{_ip} netns add {self._cfg['netns']}")

        for nic in self._cfg['nics_list']:
            self._comment(f"setup {nic['nic']}")
            if nic['type'] == 'bridge':
                self._write(f"{_ip} link add {nic['veth_prefix']}1 type veth peer name {nic['veth_prefix']}2")
                self._write(f"{_ip} link set {nic['veth_prefix']}1 netns {self._cfg['netns']}")
                self._write(f"{_ip} link set {nic['veth_prefix']}2 master {nic['nic']}")
                self._write(f"{_ip} link set {nic['veth_prefix']}2 up")
            elif nic['type'] == 'interface':
                self._write(f"{_ip} link set {nic['nic']} netns {self._cfg['netns']}")

        self._write()

    def _setup_run(self):
        self._comment(f"run container {self._cfg['container_name']}")
        self._write(f"{_podman} run \\")
        # container name
        self._write(f"\t--name {self._cfg['container_name']} \\")
        # run on background, rm
        self._write(f"\t--rm -d \\")
        # cap add
        self._write(f"\t--cap-add={','.join(self._caps)} \\")
        # cgroup
        self._write(f"\t--cgroup-parent={self._cfg['cgroup_parent']} \\")
        # cidfile, pidfile
        self._write(f"\t--cidfile=/run/{self._cfg['container_name']}-cid \\")
        self._write(f"\t--pidfile=/run/{self._cfg['container_name']}-pid \\")
        # netns
        self._write(f"\t--network=ns:{self._cfg['netns_path']} \\")
        # extra params passed to podman run
        for param in self._cfg['extra_params']:
            self._write(f"\t{param} \\")
        # rootfs & entry
        self._write(f"\t--rootfs {self._cfg['rootfs']} {' '.join(self._entry)}")


class UnitPostStop(Unit):

    def __init__(self, cfg):
        super().__init__(cfg)

    def create_unit_file(self):
        self._script_head()
        self._clean_up()
        return self._buffer.getvalue()

    def _clean_up(self):
        self._cleanup_cidpid()
        self._cleanup_netns()
        self._cleanup_container()


def _write_key_value_pair(f, k, v):
    f('='.join([str(k), str(v)]))


class SystemdUnitFile:

    def __init__(self, cfg: dict):
        self._buffer = io.StringIO()
        self._write = lambda s="": self._buffer.write(s + '\n')
        self._comment = lambda s="": self._buffer.write('# ' + s + '\n')
        self._cfg = cfg

    def create_unit_file(self):
        self._header()
        self._Unit()
        self._Service()
        self._Install()
        return self._buffer.getvalue()

    def _header(self):
        self._comment("auto generated file, DO NOT EDIT!")
        self._write()

    # render each section
    def _Unit(self):
        self._write("[Unit]")
        _write_key_value_pair(self._write, "Description", self._cfg['name'])
        self._comment("Reference: ")
        self._comment("  http://www.freedesktop.org/wiki/Software/systemd/NetworkTarget")
        _write_key_value_pair(self._write, "After", "network-online.target")
        _write_key_value_pair(self._write, "Wants", "network-online.target")
        self._write()

    def _Service(self):
        service_kv = {
            "ExecStart": f"{_bash} {self._cfg['data_path']}/unit.run",
            "ExecStop": f"-{_podman} stop {self._cfg['container_name']}",
            "ExecStopPost": f"-{_bash} {self._cfg['data_path']}/unit.poststop",
            "KillMode": "control-group",
            "Restart": "always",
            "RestartSec": "10s",
            "TimeoutStartSec": "120",
            "TimeoutStopSec": "120",
            "StartLimitInterval": "6min",
            "StartLimitBurst": "5",
            "Type": "forking",
            "PIDFile": "%t/%n-pid",
            "Delegate": "yes",
            "ExecStartPre": "-/bin/rm -f %t/%n-pid %t/%n-cid",
            "ExecStopPost": "-/bin/rm -f %t/%n-pid %t/%n-cid",
        }
        self._write("[Service]")
        for k, v in service_kv.items():
            _write_key_value_pair(self._write, k, v)
        self._write()

    def _Install(self):
        self._write("[Install]")
        _write_key_value_pair(self._write, "WantedBy", "network-online.target")
        self._write()


def main(args):
    config_file = Path(args.config)
    text_only = args.noout
    unit_run = Path(args.unit_run)
    unit_poststop = Path(args.unit_poststop)
    systemd_file = Path(args.systemd_file)

    with open(config_file, 'r') as cfg_file:
        try:
            cfg = yaml.safe_load(cfg_file)
            ur = UnitRun(cfg).create_unit_file()
            ups = UnitPostStop(cfg).create_unit_file()
            sf = SystemdUnitFile(cfg).create_unit_file()
        except Exception as e:
            print(e)

    if text_only:
        print(("\n"+"#"*64+"\n").join(["", ur, ups, sf]))
    else:
        with open(unit_run, "w") as f:
            f.write(ur)
        with open(unit_poststop, "w") as f:
            f.write(ups)
        with open(systemd_file, "w") as f:
            f.write(sf)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A script to generate unit files for openwrt on podman")
    parser.add_argument(
        "-c", "--config",
        type=str, default="config.yaml",
        help="paht of config file for openwrt on podman(default: config.yaml)",
    )
    parser.add_argument(
        "--unit-run", type=str, default="unit.run",
        help="path for storing start unit file(default: unit.run)")
    parser.add_argument(
        "--unit-poststop", type=str, default="unit.poststop",
        help="path for storing poststop unit file(default: unit.poststop)")
    parser.add_argument(
        "--systemd-file", type=str, default="openwrt-on-podman.service",
        help="path for storing systemd unit file(default: openwrt-on-podman.service)")
    parser.add_argument(
        "--noout", "--text", action="store_true",
        help="do not generate files, but print to stdout only")

    args = parser.parse_args()
    main(args)
