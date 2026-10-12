# Recovering an unbootable installation with an Ubuntu live USB

For a record containing a `migration` entry, restore the verified original manual driver using the [migration offline-recovery guidance](migration.md#failure-limits-and-offline-recovery). The stock-focused instructions below apply to ordinary installations.

First try GRUB's Advanced options and an already installed unaffected kernel, if one exists. Do not install, upgrade or downgrade a kernel as a recovery shortcut. If the target system cannot boot, use an Ubuntu live USB and select “Try Ubuntu”. The following are manual privileged operations: review each command and confirm the actual disks before executing it.

1. Identify the installed Ubuntu root filesystem with `lsblk -f`. Do not guess device names. If encrypted, unlock the correct LUKS container with your passphrase; activate its LVM volumes if applicable. Never format a partition.
2. Mount the installed root at `/mnt`. Mount a separate `/boot` partition at `/mnt/boot` if present, and its EFI partition at `/mnt/boot/efi` if applicable. Check `/mnt/etc/fstab` to ensure the correct layout before changing the initramfs.
3. Inspect `/mnt/var/lib/macbookpro13-1-ubuntu-audio/7.0.0-38-generic/install.json`. Verify that the stock path under `/mnt/lib/modules/7.0.0-38-generic/kernel/` still exists and matches `stock_sha256`, using `sha256sum`. Current schema-2 records store `stock_relative` beneath the kernel module directory; older schema-1 records use `stock_path`. Do not copy a backup over it automatically. If stock is missing or changed, stop and investigate package integrity.
4. Locate only this project's override:

   `/mnt/lib/modules/7.0.0-38-generic/updates/macbookpro13-1-ubuntu-audio/snd-hda-codec-cs8409.ko`

   Check its hash against `custom_sha256` if present. Move it outside `/mnt/lib/modules/`, for example to `/mnt/root/cs8409-recovery/` (create that directory manually). Do not move or delete the stock module. A missing override can mean installation failed earlier; still refresh indexes and initramfs if they might contain it.
5. Bind the live environment's device and virtual filesystems, then enter the installed system:

```sh
sudo mount --rbind /dev /mnt/dev
sudo mount --make-rslave /mnt/dev
sudo mount --rbind /proc /mnt/proc
sudo mount --make-rslave /mnt/proc
sudo mount --rbind /sys /mnt/sys
sudo mount --make-rslave /mnt/sys
sudo mount --rbind /run /mnt/run
sudo mount --make-rslave /mnt/run
sudo chroot /mnt /bin/bash
```

6. Inside the chroot, regenerate the target kernel's module index (the live kernel's `uname -r` is irrelevant):

```sh
depmod -a 7.0.0-38-generic
modinfo -k 7.0.0-38-generic -n snd_hda_codec_cs8409
# Inspect before deciding whether an initramfs refresh is needed:
lsinitramfs /boot/initrd.img-7.0.0-38-generic | grep cs8409
# Only if the image contains the codec/removed override, refresh manually:
# update-initramfs -u -k 7.0.0-38-generic
exit
```

Confirm `modinfo` selects the untouched module under `kernel/`, and, if a refresh was required and explicitly performed, that `update-initramfs` succeeds. Do not reboot after a failed refresh; inspect the error and mounted `/boot` filesystem first. The normal rollback script intentionally refuses to run against the live USB kernel, so these targeted manual steps are required.

7. Unmount bind mounts and target partitions in reverse order, then reboot manually and remove the USB. Do not force unmount busy filesystems; exit shells and applications using them first. Retain the recovered module and install record for diagnosis.

No blacklist, modprobe configuration, boot argument, firmware change, or DKMS entry is created by this project, so none needs undoing. Recovery restores the pre-project stock audio behavior; it does not promise working speakers with stock.
