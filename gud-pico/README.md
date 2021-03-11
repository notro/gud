Raspberry Pi Pico GUD USB Display
---------------------------------

GUD implementation for the Raspberry Pi Pico with a [Pimoroni Pico Display](https://shop.pimoroni.com/products/pico-display-pack).

tinyusb needs to be patched:
```diff
diff --git a/src/device/usbd.c b/src/device/usbd.c
index 90edc3dd..054517ef 100644
--- a/src/device/usbd.c
+++ b/src/device/usbd.c
@@ -578,6 +578,7 @@ static bool process_control_request(uint8_t rhport, tusb_control_request_t const

   TU_ASSERT(p_request->bmRequestType_bit.type < TUSB_REQ_TYPE_INVALID);

+/*
   // Vendor request
   if ( p_request->bmRequestType_bit.type == TUSB_REQ_TYPE_VENDOR )
   {
@@ -586,6 +587,7 @@ static bool process_control_request(uint8_t rhport, tusb_control_request_t const
     if (tud_vendor_control_complete_cb) usbd_control_set_complete_callback(tud_vendor_control_complete_cb);
     return tud_vendor_control_request_cb(rhport, p_request);
   }
+*/

 #if CFG_TUSB_DEBUG >= 2
   if (TUSB_REQ_TYPE_STANDARD == p_request->bmRequestType_bit.type && p_request->bRequest <= TUSB_REQ_SYNCH_FRAME)
```

The ```PICO_SDK_PATH``` env var should point to the Pico SDK.

Build
```
$ git clone https://github.com/notro/gud
$ cd gud/gud-pico
$ mkdir build && cd build
$ cmake ..
$ make

```

TODO:
- Find the proper fix for the tinyusb issue
- See if it's possible to use unlz4. It works with the test image in ```modetest``` but hangs when flipping ```modetest -v```
