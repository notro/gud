/**
  ******************************************************************************
  * @file    usbd_msc.h
  * @author  MCD Application Team
  * @brief   Header for the usbd_msc.c file
  ******************************************************************************
  * @attention
  *
  * <h2><center>&copy; Copyright (c) 2015 STMicroelectronics.
  * All rights reserved.</center></h2>
  *
  * This software component is licensed by ST under Ultimate Liberty license
  * SLA0044, the "License"; You may not use this file except in compliance with
  * the License. You may obtain a copy of the License at:
  *                      http://www.st.com/SLA0044
  *
  ******************************************************************************
  */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __USBD_MSC_H
#define __USBD_MSC_H

#ifdef __cplusplus
 extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include  "usbd_ioreq.h"

#include "gud.h"

#define MSC_MAX_FS_PACKET            0x40U
#define MSC_MAX_HS_PACKET            0x200U

#define USB_MSC_CONFIG_DESC_SIZ      25

#define MSC_EPOUT_ADDR               0x01U

typedef struct
{
  uint32_t interface;
  struct gud_drm_gadget gdg;
  uint8_t buf[GUD_DRM_MAX_TRANSFER_SIZE];

  int errno;
  int status_pending;

  uint8_t bRequest;
  uint16_t wValue;
  uint16_t wLength;

  struct gud_drm_req_set_buffer set_buf_req;

  int set_buf;
  uint32_t received;
}
USBD_GUD_HandleTypeDef;



/* Structure for MSC process */
extern USBD_ClassTypeDef  USBD_MSC;
#define USBD_MSC_CLASS    &USBD_MSC

void USBD_GUD_process (USBD_HandleTypeDef *pdev);

#ifdef __cplusplus
}
#endif

#endif  /* __USBD_MSC_H */
/**
  * @}
  */

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/
