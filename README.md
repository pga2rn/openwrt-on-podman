# openwrt-on-podman

This repository includes a script and sample config file for setting up openwrt as docker container on host machine via podman.
The script generates a systemd service unit file along with unit.start and unit.stop scripts.

# Usage
1. Download and export openwrt rootfs tarball (generic-ext4-rootfs.img.gz),
2. Adjust config.yaml accordingly (check the sample config.yaml for details),
3. Run gen_script.py to generate unit.start, unit.stop and <config.service_name>.service,
4. Install and enable the generated <config.service_name>.service.
For more details, please refer to the sample config.yaml.

# NOTE
1. Due to the behavior mentioned in https://github.com/moby/moby/issues/34337, the fw3 doesn't work as expected.
Please include the preboot.init.d into /etc/init.d and enable it to avoid this issue.
2. Please load the needed kernel modules on the host machine before start the openwrt container. I may implement loading these modules on start in the future.
3. ~~If you want to change sysctl options related to network, please change it by executing `ip netns <netns> exec sysctl -w <key>=<value>`. I may include these as optional params in the config in the future.~~ Use config.sysctl directories in the config.yaml to config sysctl params.
