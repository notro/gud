
#ifndef _DRM_H_
#define _DRM_H_

#include <stdint.h>

#if defined(__cplusplus)
extern "C" {
#endif


#include <stddef.h>
#include <stdint.h>

typedef uint8_t  __u8;
typedef uint16_t __u16;
typedef uint32_t __u32;
typedef uint64_t __u64;

typedef int32_t __s32;

typedef uint16_t __le16;
typedef uint32_t __le32;
typedef uint64_t __le64;

#define __packed                        __attribute__((__packed__))

#define BIT(n)	(1U << n)

#define EIO		5
#define	EINVAL		22


#define USB_TYPE_VENDOR			(0x02 << 5)




#if defined(__cplusplus)
}
#endif

#endif
