# stop /dev/ttyACM0 losing its permissions on every badge reboot.
#
# the device node is recreated each time the badge re-enumerates, so a manual
# `chmod o+rw` evaporates. at a con that is a chmod every power cycle, and every one
# of them needs a password prompt on a machine where the global git config is
# read-only and sudo has no askpass.
#
# import this from the nixfiles (or paste the two stanzas) and rebuild once.

{ ... }:

{
  # the plain fix: be in the group that already owns the node.
  # needs a re-login (or `newgrp dialout`) to take effect in existing sessions.
  users.users.quaver.extraGroups = [ "dialout" ];

  # the belt-and-braces fix: tag the badge specifically so logind grants the
  # seat-local user access via uaccess, the same mechanism that already makes
  # /dev/hidraw0 work without any of this. matches only the baochip VID:PID, so it
  # does not widen access to every serial device on the machine.
  services.udev.extraRules = ''
    SUBSYSTEM=="tty", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6198", TAG+="uaccess", SYMLINK+="badge"
    SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6198", TAG+="uaccess"
  '';

  # with the SYMLINK above, the tools can take --port /dev/badge and stop caring
  # which ttyACM number the badge landed on this time.
}
