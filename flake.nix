{
  description = "def con 34 badge ctf .. offline-capable RE/badge-hacking toolchain";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" "x86_64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs:
        let
          isLinux = pkgs.stdenv.hostPlatform.isLinux;

          python = pkgs.python3.withPackages (ps: with ps; [
            pwntools
            pyserial
            pyusb
            requests
            pillow
            crcmod
            intelhex
            capstone
            keystone-engine
            unicorn
            pycryptodome
            numpy
          ]);
        in
        pkgs.mkShell {
          name = "dc34";

          packages = with pkgs; [
            python

            # --- static RE ---
            radare2
            binwalk
            ghidra
            yara
            binutils # objdump/readelf/strings for the odd ELF
            file
            hexyl

            # --- microcontroller flashing / debug ---
            openocd
            probe-rs-tools # rp2040 / stm32 / nrf over cmsis-dap, swd
            picotool # rp2040: info, save, load, reboot
            esptool # esp32: flash_id, read_flash, otp
            dfu-util

            # --- serial / logic / bus ---
            picocom
            sigrok-cli
            flashrom # spi flash, chip-off or in-circuit clip

            # --- rf ---
            rtl-sdr
            hackrf

            # --- misc con-floor utility ---
            usbutils
            zbar # decode qr codes off the panel
            jq
            ripgrep
            sqlite
          ] ++ pkgs.lib.optionals isLinux [
            # the gui/rf half of the kit is linux-only in nixpkgs. on the mac these
            # are absent by design rather than broken: do the visual work on the
            # framework, keep the mac for static RE and scripting.
            pulseview # gui logic viewer
            inspectrum # visual burst inspection of iq captures
            urh # universal radio hacker: demod + protocol guessing
            android-tools # adb, in case the badge speaks usb gadget
          ];

          shellHook = ''
            export DC34_ROOT="$PWD"
            export GHIDRA_INSTALL_DIR="${pkgs.ghidra}/lib/ghidra"
            echo "dc34 shell up. root=$DC34_ROOT"
            echo "dump firmware before you poke it. firmware/MANIFEST.md is the ledger."
          '';
        });
    };
}
