################################################################################
#
# hidg-touch
#
################################################################################

HIDG_TOUCH_BRIDGE_LICENSE = MIT

define HIDG_TOUCH_EXTRACT_CMDS
	cp $(HIDG_TOUCH_PKGDIR)/usb_desc.c $(@D)/
	cp $(HIDG_TOUCH_PKGDIR)/hidg-touch.c $(@D)/
endef

define HIDG_TOUCH_BUILD_CMDS
	(cd $(@D); $(TARGET_CC) -Wall -Os -levdev -I$(STAGING_DIR)/usr/include/libevdev-1.0 -o hidg-touch usb_desc.c hidg-touch.c)
endef

define HIDG_TOUCH_INSTALL_TARGET_CMDS
	install -m 0755 -D $(@D)/hidg-touch $(TARGET_DIR)/usr/bin/hidg-touch
endef

$(eval $(generic-package))
