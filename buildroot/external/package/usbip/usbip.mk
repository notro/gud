################################################################################
#
# usbip
#
################################################################################

# No USBIP_SITE, no USBIP_VERSION, we vampirise the code from the
# linux kernel
USBIP_DEPENDENCIES = udev linux

USBIP_AUTORECONF = YES
USBIP_CONF_OPTS = --without-tcp-wrappers

USBIP_SRC_DIR = $(wildcard \
  $(LINUX_DIR)/tools/usb/usbip \
  $(LINUX_DIR)/drivers/staging/usbip/userspace)

define USBIP_EXTRACT_CMDS
	if [ -z "$(USBIP_SRC_DIR)" ]; then \
	    echo "No usbip source in your kernel tree" 2>&1; \
	    exit 1; \
	fi
	rsync -au --chmod=u=rwX,go=rX $(RSYNC_VCS_EXCLUSIONS) $(USBIP_SRC_DIR)/ $(@D)
endef

$(eval $(autotools-package))
