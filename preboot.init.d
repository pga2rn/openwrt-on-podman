#!/bin/sh /etc/rc.common
# Copyright (C) 2006 OpenWrt.org

# workaround to fix fw3 not working properly in docker environment
# Reference:
#   https://github.com/openwrt/openwrt/pull/2525/files
#   https://github.com/moby/moby/issues/34337

START=00
boot() {
        for t in filter nat mangle raw
        do
                /usr/sbin/ip6tables -t ${t} -L > /dev/null 2>&1
                /usr/sbin/iptables -t ${t} -L > /dev/null 2>&1
        done
        sleep 1
}