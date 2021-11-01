# openwrt-on-podman

This repository includes a script and sample config file for setting up openwrt as docker container on host machine via podman.
The script generates a systemd service unit file along with unit.start and unit.stop scripts.

# NOTE
1. Due to the behavior mentioned in https://github.com/moby/moby/issues/34337, the fw3 doesn't work as expected.
Please include the preboot.init.d into /etc/init.d and enable it to avoid this issue.
2. Please load the needed kernel modules on the host machine before start the openwrt container.
3. If you want to change sysctl options related to network, please change it by executing `ip netns <netns> exec sysctl -w <key>=<value>`. I may include these as optional params in the config in the future.
