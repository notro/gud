/**
  ******************************************************************************
  * @file    usbd_msc.c
  * @author  MCD Application Team
  * @brief   This file provides all the MSC core functions.
  *
  * @verbatim
  *
  *          ===================================================================
  *                                MSC Class  Description
  *          ===================================================================
  *           This module manages the MSC class V1.0 following the "Universal
  *           Serial Bus Mass Storage Class (MSC) Bulk-Only Transport (BOT) Version 1.0
  *           Sep. 31, 1999".
  *           This driver implements the following aspects of the specification:
  *             - Bulk-Only Transport protocol
  *             - Subclass : SCSI transparent command set (ref. SCSI Primary Commands - 3 (SPC-3))
  *
  *  @endverbatim
  *
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

/* Portions added for GUD are licensed: CC0-1.0 */


  /* BSPDependencies
  - "stm32xxxxx_{eval}{discovery}{nucleo_144}.c"
  - "stm32xxxxx_{eval}{discovery}_io.c"
  - "stm32xxxxx_{eval}{discovery}{adafruit}_sd.c"
  EndBSPDependencies */

/* Includes ------------------------------------------------------------------*/
#include "usbd_msc.h"


// for INTERNAL_BUFFER_START_ADDRESS
#include "main.h"

/* USB Mass storage device Configuration Descriptor */
/*   All Descriptors (Configuration, Interface, Endpoint, Class, Vendor */
__ALIGN_BEGIN uint8_t USBD_MSC_CfgHSDesc[USB_MSC_CONFIG_DESC_SIZ]  __ALIGN_END =
{

  0x09,   /* bLength: Configuation Descriptor size */
  USB_DESC_TYPE_CONFIGURATION,   /* bDescriptorType: Configuration */
  USB_MSC_CONFIG_DESC_SIZ,

  0x00,
  0x01,   /* bNumInterfaces: 1 interface */
  0x01,   /* bConfigurationValue: */
  0x00,   /* iConfiguration: */
  0xC0,   /* bmAttributes: */
  0x32,   /* MaxPower 100 mA */

  /********************  Mass Storage interface ********************/
  0x09,   /* bLength: Interface Descriptor size */
  0x04,   /* bDescriptorType: */
  0x00,   /* bInterfaceNumber: Number of Interface */
  0x00,   /* bAlternateSetting: Alternate setting */
  0x01,   /* bNumEndpoints*/
  0xff,   /* bInterfaceClass: Vendor Class */
  0x00,   /* bInterfaceSubClass : */
  0x00,   /* nInterfaceProtocol */
  0x05,          /* iInterface: */
  /********************  Mass Storage Endpoints ********************/
  0x07,   /*Endpoint descriptor length = 7 */
  0x05,   /*Endpoint descriptor type */
  MSC_EPOUT_ADDR,   /*Endpoint address (OUT, address 1) */
  0x02,   /*Bulk endpoint type */
  LOBYTE(MSC_MAX_HS_PACKET),
  HIBYTE(MSC_MAX_HS_PACKET),
  0x00     /*Polling interval in milliseconds*/
};

/* USB Mass storage device Configuration Descriptor */
/*   All Descriptors (Configuration, Interface, Endpoint, Class, Vendor */
uint8_t USBD_MSC_CfgFSDesc[USB_MSC_CONFIG_DESC_SIZ]  __ALIGN_END =
{

  0x09,   /* bLength: Configuation Descriptor size */
  USB_DESC_TYPE_CONFIGURATION,   /* bDescriptorType: Configuration */
  USB_MSC_CONFIG_DESC_SIZ,

  0x00,
  0x01,   /* bNumInterfaces: 1 interface */
  0x01,   /* bConfigurationValue: */
  0x04,   /* iConfiguration: */
  0xC0,   /* bmAttributes: */
  0x32,   /* MaxPower 100 mA */

  /********************  Mass Storage interface ********************/
  0x09,   /* bLength: Interface Descriptor size */
  0x04,   /* bDescriptorType: */
  0x00,   /* bInterfaceNumber: Number of Interface */
  0x00,   /* bAlternateSetting: Alternate setting */
  0x02,   /* bNumEndpoints*/
  0x08,   /* bInterfaceClass: MSC Class */
  0x06,   /* bInterfaceSubClass : SCSI transparent*/
  0x50,   /* nInterfaceProtocol */
  0x05,          /* iInterface: */
  /********************  Mass Storage Endpoints ********************/
  0x07,   /*Endpoint descriptor length = 7 */
  0x05,   /*Endpoint descriptor type */
  MSC_EPOUT_ADDR,   /*Endpoint address (OUT, address 1) */
  0x02,   /*Bulk endpoint type */
  LOBYTE(MSC_MAX_FS_PACKET),
  HIBYTE(MSC_MAX_FS_PACKET),
  0x00     /*Polling interval in milliseconds*/
};

__ALIGN_BEGIN uint8_t USBD_MSC_OtherSpeedCfgDesc[USB_MSC_CONFIG_DESC_SIZ]   __ALIGN_END  =
{

  0x09,   /* bLength: Configuation Descriptor size */
  USB_DESC_TYPE_OTHER_SPEED_CONFIGURATION,
  USB_MSC_CONFIG_DESC_SIZ,

  0x00,
  0x01,   /* bNumInterfaces: 1 interface */
  0x01,   /* bConfigurationValue: */
  0x04,   /* iConfiguration: */
  0xC0,   /* bmAttributes: */
  0x32,   /* MaxPower 100 mA */

  /********************  Mass Storage interface ********************/
  0x09,   /* bLength: Interface Descriptor size */
  0x04,   /* bDescriptorType: */
  0x00,   /* bInterfaceNumber: Number of Interface */
  0x00,   /* bAlternateSetting: Alternate setting */
  0x02,   /* bNumEndpoints*/
  0x08,   /* bInterfaceClass: MSC Class */
  0x06,   /* bInterfaceSubClass : SCSI transparent command set*/
  0x50,   /* nInterfaceProtocol */
  0x05,          /* iInterface: */
  /********************  Mass Storage Endpoints ********************/
  0x07,   /*Endpoint descriptor length = 7 */
  0x05,   /*Endpoint descriptor type */
  MSC_EPOUT_ADDR,   /*Endpoint address (OUT, address 1) */
  0x02,   /*Bulk endpoint type */
  0x40,
  0x00,
  0x00     /*Polling interval in milliseconds*/
};

/* USB Standard Device Descriptor */
__ALIGN_BEGIN  uint8_t USBD_MSC_DeviceQualifierDesc[USB_LEN_DEV_QUALIFIER_DESC]  __ALIGN_END =
{
  USB_LEN_DEV_QUALIFIER_DESC,
  USB_DESC_TYPE_DEVICE_QUALIFIER,
  0x00,
  0x02,
  0x00,
  0x00,
  0x00,
  MSC_MAX_FS_PACKET,
  0x01,
  0x00,
};

static uint8_t bulk_buf[BULK_BUF_LEN];

#define BUFFER_ADDRESS  INTERNAL_BUFFER_START_ADDRESS
//#define BUFFER_ADDRESS  bulk_buf

/**
  * @brief  USBD_MSC_Init
  *         Initialize  the mass storage configuration
  * @param  pdev: device instance
  * @param  cfgidx: configuration index
  * @retval status
  */
static uint8_t  USBD_MSC_Init (USBD_HandleTypeDef *pdev, uint8_t cfgidx)
{
  if(pdev->dev_speed == USBD_SPEED_HIGH)
  {
    /* Open EP OUT */
    USBD_LL_OpenEP(pdev, MSC_EPOUT_ADDR, USBD_EP_TYPE_BULK, MSC_MAX_HS_PACKET);
    pdev->ep_out[MSC_EPOUT_ADDR & 0xFU].is_used = 1U;
  }
  else
  {
    /* Open EP OUT */
    USBD_LL_OpenEP(pdev, MSC_EPOUT_ADDR, USBD_EP_TYPE_BULK, MSC_MAX_FS_PACKET);
    pdev->ep_out[MSC_EPOUT_ADDR & 0xFU].is_used = 1U;
  }

  return USBD_OK;
}

/**
  * @brief  USBD_MSC_DeInit
  *         DeInitilaize  the mass storage configuration
  * @param  pdev: device instance
  * @param  cfgidx: configuration index
  * @retval status
  */
static uint8_t  USBD_MSC_DeInit (USBD_HandleTypeDef *pdev,
                                 uint8_t cfgidx)
{
  /* Close MSC EPs */
  USBD_LL_CloseEP(pdev, MSC_EPOUT_ADDR);
  pdev->ep_out[MSC_EPOUT_ADDR & 0xFU].is_used = 0U;

  return USBD_OK;
}


/**
  * @brief  Copy and convert image (LAYER_SIZE_X, LAYER_SIZE_Y) of format RGB565
  * to LCD frame buffer area centered in WVGA resolution.
  * The area of copy is of size (LAYER_SIZE_X, LAYER_SIZE_Y) in ARGB8888.
  * @param  pSrc: Pointer to source buffer : source image buffer start here
  * @param  pDst: Pointer to destination buffer LCD frame buffer center area start here
  * @param  xSize: Buffer width (LAYER_SIZE_X here)
  * @param  ySize: Buffer height (LAYER_SIZE_Y here)
  * @retval LCD Status : LCD_OK or LCD_ERROR
  */

/*
  offset_address_area_blended_image_in_lcd_buffer =  ((((WVGA_RES_Y - LAYER_SIZE_Y) / 2) * WVGA_RES_X)
                                                    +   ((WVGA_RES_X - LAYER_SIZE_X) / 2))
                                                    * ARGB8888_BYTE_PER_PIXEL;

    lcd_status = CopyImageToLcdFrameBuffer((void*)&(aBlendedImage[0]),
                                                (void*)(LCD_FRAME_BUFFER + offset_address_area_blended_image_in_lcd_buffer),
                                                LAYER_SIZE_X,
                                                LAYER_SIZE_Y);
*/

static DMA2D_HandleTypeDef hdma2d;

static uint8_t CopyImageToLcdFrameBuffer(void *pDst, void *pSrc, uint32_t x, uint32_t y, uint32_t width, uint32_t height)
{
  HAL_StatusTypeDef hal_status = HAL_OK;
  uint8_t lcd_status = LCD_ERROR;

  pDst += ((y * 800) + x) * 2;

  /* Configure the DMA2D Mode, Color Mode and output offset */
  hdma2d.Init.Mode         = DMA2D_M2M_PFC;

//  hdma2d_discovery.Init.ColorMode    = DMA2D_OUTPUT_ARGB8888; /* Output color out of PFC */
  hdma2d.Init.ColorMode    = DMA2D_OUTPUT_RGB565; /* Output color out of PFC */

  hdma2d.Init.AlphaInverted = DMA2D_REGULAR_ALPHA;  /* No Output Alpha Inversion*/
  hdma2d.Init.RedBlueSwap   = DMA2D_RB_REGULAR;     /* No Output Red & Blue swap */

  /* Output offset in pixels == nb of pixels to be added at end of line to come to the  */
  /* first pixel of the next line : on the output side of the DMA2D computation         */
//  hdma2d_discovery.Init.OutputOffset = (WVGA_RES_X - LAYER_SIZE_X);
  hdma2d.Init.OutputOffset = (800 - width);

  /* Foreground Configuration */
  hdma2d.LayerCfg[0].AlphaMode = DMA2D_NO_MODIF_ALPHA;
  hdma2d.LayerCfg[0].InputAlpha = 0xFF; /* fully opaque */
  hdma2d.LayerCfg[0].InputColorMode = DMA2D_INPUT_RGB565;
  hdma2d.LayerCfg[0].InputOffset = 0;
  hdma2d.LayerCfg[0].RedBlueSwap = DMA2D_RB_REGULAR; /* No ForeGround Red/Blue swap */
  hdma2d.LayerCfg[0].AlphaInverted = DMA2D_REGULAR_ALPHA; /* No ForeGround Alpha inversion */

  hdma2d.Instance = DMA2D;

  /* DMA2D Initialization */
  if(HAL_DMA2D_Init(&hdma2d) == HAL_OK)
  {
    if(HAL_DMA2D_ConfigLayer(&hdma2d, 1) == HAL_OK)
    {
      if (HAL_DMA2D_Start(&hdma2d, (uint32_t)pSrc, (uint32_t)pDst, width, height) == HAL_OK)
      {
        /* Polling For DMA transfer */
        hal_status = HAL_DMA2D_PollForTransfer(&hdma2d, 10);
        if(hal_status == HAL_OK)
        {
          /* return good status on exit */
          lcd_status = LCD_OK;
        }
      }
    }
  }

  return(lcd_status);
}

void USBD_GUD_process (USBD_HandleTypeDef *pdev)
{
  USBD_GUD_HandleTypeDef *hgdg = pdev->pUserData;
  int status;

  if (hgdg->received)
  {
    if (0)
      CopyImageToLcdFrameBuffer((void *)LCD_FB_START_ADDRESS, (void *)BUFFER_ADDRESS,
                                hgdg->set_buf_req.x, hgdg->set_buf_req.y, hgdg->set_buf_req.width, hgdg->set_buf_req.height);
    else
      gud_drm_gadget_write_buffer(&hgdg->gdg, (void *)LCD_FB_START_ADDRESS, (void *)BUFFER_ADDRESS, hgdg->received);

    hgdg->received = 0;
  }

  if (hgdg->set_buf)
  {
    status = gud_drm_gadget_set_buffer(&hgdg->gdg, &hgdg->set_buf_req);
    if (status < 0) {
      hgdg->errno = -status;
    } else {
      USBD_LL_PrepareReceive (pdev, MSC_EPOUT_ADDR, (void *)BUFFER_ADDRESS, status);
    }

    hgdg->set_buf = 0;
    hgdg->status_pending = 0;
  }
}

static uint8_t USBD_GUD_ctrl_set (USBD_HandleTypeDef *pdev, uint8_t bRequest, uint16_t wValue, uint16_t wLength)
{
  USBD_GUD_HandleTypeDef *hgdg = pdev->pUserData;
  int status = -EINVAL;

  if (bRequest == GUD_DRM_USB_REQ_SET_BUFFER)
  {
    if (wLength == sizeof(struct gud_drm_req_set_buffer)) {
      struct gud_drm_req_set_buffer *set_buf_req = (struct gud_drm_req_set_buffer *)hgdg->buf;

      hgdg->set_buf_req = *set_buf_req;
      hgdg->set_buf = 1;
      status = 0;
    }
  } else {
    status = gud_drm_gadget_ctrl_set(&hgdg->gdg, bRequest, wValue, hgdg->buf, wLength);
    hgdg->status_pending = 0;
  }

  if (status < 0) {
    hgdg->errno = -status;
    hgdg->status_pending = 0;
  }

  return USBD_OK;
}

static uint8_t  USBD_MSC_Setup_Vendor (USBD_HandleTypeDef *pdev, USBD_SetupReqTypedef *req)
{
  USBD_GUD_HandleTypeDef *hgdg = pdev->pUserData;
  int status;

  //if ((req->bmRequest & USB_REQ_RECIPIENT_MASK) != USB_REQ_RECIPIENT_INTERFACE || hgdg->interface != req->wIndex)
  if ((req->bmRequest & USB_REQ_RECIPIENT_MASK) != USB_REQ_RECIPIENT_INTERFACE)
    return USBD_FAIL;

  if (req->wLength > GUD_DRM_MAX_TRANSFER_SIZE)
    return USBD_FAIL;

  if (req->bRequest == 0x00) { // USB_REQ_GET_STATUS
    struct gud_drm_req_get_status *reqstat = (struct gud_drm_req_get_status *)hgdg->buf;

    if (req->wLength != sizeof(*reqstat))
      return USBD_FAIL;

    reqstat->flags = 0;
    if (hgdg->status_pending)
      reqstat->flags |= GUD_DRM_STATUS_PENDING;
    reqstat->errno = hgdg->errno;

    USBD_CtlSendData (pdev, hgdg->buf, req->wLength);
    return USBD_OK;
  }

  hgdg->status_pending = 0;
  hgdg->errno = 0;

  if (req->bmRequest & 0x80) {
      status = gud_drm_gadget_ctrl_get(&hgdg->gdg, req->bRequest, req->wValue, hgdg->buf, req->wLength);
      if (status < 0) {
        hgdg->errno = -status;
        return USBD_FAIL;
      }

      USBD_CtlSendData (pdev, hgdg->buf, status);
  } else {
    if (req->wLength) {
      USBD_CtlPrepareRx (pdev, hgdg->buf, req->wLength);
      hgdg->bRequest = req->bRequest;
      hgdg->wValue = req->wValue;
      hgdg->wLength = req->wLength;
      hgdg->status_pending = 1;
      status = 0;
    } else {
      return USBD_GUD_ctrl_set (pdev, req->bRequest, req->wValue, req->wLength);
      status = 0;
    }
  }

  return USBD_OK;
}

/**
* @brief  USBD_MSC_Setup
*         Handle the MSC specific requests
* @param  pdev: device instance
* @param  req: USB request
* @retval status
*/
static uint8_t  USBD_MSC_Setup (USBD_HandleTypeDef *pdev, USBD_SetupReqTypedef *req)
{
  USBD_GUD_HandleTypeDef *hgdg = pdev->pUserData;
  uint8_t ret = USBD_OK;
  uint16_t status_info = 0U;

  switch (req->bmRequest & USB_REQ_TYPE_MASK)
  {
  case USB_REQ_TYPE_VENDOR:
    ret = USBD_MSC_Setup_Vendor (pdev, req);
    if (ret == USBD_FAIL)
      USBD_CtlError (pdev, req);
    break;

    /* Interface & Endpoint request */
  case USB_REQ_TYPE_STANDARD:
    switch (req->bRequest)
    {
    case USB_REQ_GET_STATUS:
      if (pdev->dev_state == USBD_STATE_CONFIGURED)
      {
        USBD_CtlSendData (pdev, (uint8_t *)(void *)&status_info, 2U);
      }
      else
      {
        USBD_CtlError (pdev, req);
        ret = USBD_FAIL;
      }
      break;

    case USB_REQ_GET_INTERFACE:
      if (pdev->dev_state == USBD_STATE_CONFIGURED)
      {
        USBD_CtlSendData (pdev, (uint8_t *)(void *)&hgdg->interface, 1U);
      }
      else
      {
        USBD_CtlError (pdev, req);
        ret = USBD_FAIL;
      }
      break;

    case USB_REQ_SET_INTERFACE:
      if (pdev->dev_state == USBD_STATE_CONFIGURED)
      {
        hgdg->interface = (uint8_t)(req->wValue);
      }
      else
      {
        USBD_CtlError (pdev, req);
        ret = USBD_FAIL;
      }
      break;

    case USB_REQ_CLEAR_FEATURE:

      /* Flush the FIFO and Clear the stall status */
      USBD_LL_FlushEP(pdev, (uint8_t)req->wIndex);

      /* Reactivate the EP */
      USBD_LL_CloseEP (pdev , (uint8_t)req->wIndex);
      if((((uint8_t)req->wIndex) & 0x80U) == 0x80U)
      {
        pdev->ep_in[(uint8_t)req->wIndex & 0xFU].is_used = 0U;
      }
      else
      {
        pdev->ep_out[(uint8_t)req->wIndex & 0xFU].is_used = 0U;
        if(pdev->dev_speed == USBD_SPEED_HIGH)
        {
          /* Open EP OUT */
          USBD_LL_OpenEP(pdev, MSC_EPOUT_ADDR, USBD_EP_TYPE_BULK,
                         MSC_MAX_HS_PACKET);
        }
        else
        {
          /* Open EP OUT */
          USBD_LL_OpenEP(pdev, MSC_EPOUT_ADDR, USBD_EP_TYPE_BULK,
                         MSC_MAX_FS_PACKET);
        }
        pdev->ep_out[MSC_EPOUT_ADDR & 0xFU].is_used = 1U;
      }
      break;

    default:
      USBD_CtlError (pdev, req);
      ret = USBD_FAIL;
      break;
    }
    break;

  default:
    USBD_CtlError (pdev, req);
    ret = USBD_FAIL;
    break;
  }

  return ret;
}

static uint8_t USBD_MSC_EP0_RxReady (USBD_HandleTypeDef *pdev)
{
  USBD_GUD_HandleTypeDef *hgdg = pdev->pUserData;

  // FIXME: check length how?

  USBD_GUD_ctrl_set (pdev, hgdg->bRequest, hgdg->wValue, hgdg->wLength);

  return USBD_OK;
}

/**
* @brief  USBD_MSC_DataOut
*         handle data OUT Stage
* @param  pdev: device instance
* @param  epnum: endpoint index
* @retval status
*/
static uint8_t  USBD_MSC_DataOut (USBD_HandleTypeDef *pdev,
                               uint8_t epnum)
{
  USBD_GUD_HandleTypeDef *hgdg = pdev->pUserData;

  hgdg->received = USBD_LL_GetRxDataSize (pdev, MSC_EPOUT_ADDR);

  return USBD_OK;
}

/**
* @brief  USBD_MSC_GetHSCfgDesc
*         return configuration descriptor
* @param  length : pointer data length
* @retval pointer to descriptor buffer
*/
static uint8_t  *USBD_MSC_GetHSCfgDesc (uint16_t *length)
{
  *length = sizeof (USBD_MSC_CfgHSDesc);
  return USBD_MSC_CfgHSDesc;
}

/**
* @brief  USBD_MSC_GetFSCfgDesc
*         return configuration descriptor
* @param  length : pointer data length
* @retval pointer to descriptor buffer
*/
static uint8_t  *USBD_MSC_GetFSCfgDesc (uint16_t *length)
{
  *length = sizeof (USBD_MSC_CfgFSDesc);
  return USBD_MSC_CfgFSDesc;
}

/**
* @brief  USBD_MSC_GetOtherSpeedCfgDesc
*         return other speed configuration descriptor
* @param  length : pointer data length
* @retval pointer to descriptor buffer
*/
static uint8_t  *USBD_MSC_GetOtherSpeedCfgDesc (uint16_t *length)
{
  *length = sizeof (USBD_MSC_OtherSpeedCfgDesc);
  return USBD_MSC_OtherSpeedCfgDesc;
}
/**
* @brief  DeviceQualifierDescriptor
*         return Device Qualifier descriptor
* @param  length : pointer data length
* @retval pointer to descriptor buffer
*/
static uint8_t  *USBD_MSC_GetDeviceQualifierDescriptor (uint16_t *length)
{
  *length = sizeof (USBD_MSC_DeviceQualifierDesc);
  return USBD_MSC_DeviceQualifierDesc;
}

USBD_ClassTypeDef  USBD_MSC =
{
  USBD_MSC_Init,
  USBD_MSC_DeInit,
  USBD_MSC_Setup,
  NULL, /*EP0_TxSent*/
  USBD_MSC_EP0_RxReady,
  NULL, /* DataIn */
  USBD_MSC_DataOut,
  NULL, /*SOF */
  NULL,
  NULL,
  USBD_MSC_GetHSCfgDesc,
  USBD_MSC_GetFSCfgDesc,
  USBD_MSC_GetOtherSpeedCfgDesc,
  USBD_MSC_GetDeviceQualifierDescriptor,
};

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/
