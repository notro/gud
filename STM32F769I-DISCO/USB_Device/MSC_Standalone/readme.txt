/**
  @page MSC_Standalone USB Device Mass Storage (MSC) application
  
  @verbatim
  ******************************************************************************
  * @file    USB_Device/MSC_Standalone/readme.txt 
  * @author  MCD Application Team
  * @brief   Description of the USB Device MSC application.
  ******************************************************************************
  *
  * Copyright (c) 2017 STMicroelectronics International N.V. All rights reserved.
  *
  * Redistribution and use in source and binary forms, with or without 
  * modification, are permitted, provided that the following conditions are met:
  *
  * 1. Redistribution of source code must retain the above copyright notice, 
  *    this list of conditions and the following disclaimer.
  * 2. Redistributions in binary form must reproduce the above copyright notice,
  *    this list of conditions and the following disclaimer in the documentation
  *    and/or other materials provided with the distribution.
  * 3. Neither the name of STMicroelectronics nor the names of other 
  *    contributors to this software may be used to endorse or promote products 
  *    derived from this software without specific written permission.
  * 4. This software, including modifications and/or derivative works of this 
  *    software, must execute solely and exclusively on microcontroller or
  *    microprocessor devices manufactured by or for STMicroelectronics.
  * 5. Redistribution and use of this software other than as permitted under 
  *    this license is void and will automatically terminate your rights under 
  *    this license. 
  *
  * THIS SOFTWARE IS PROVIDED BY STMICROELECTRONICS AND CONTRIBUTORS "AS IS" 
  * AND ANY EXPRESS, IMPLIED OR STATUTORY WARRANTIES, INCLUDING, BUT NOT 
  * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
  * PARTICULAR PURPOSE AND NON-INFRINGEMENT OF THIRD PARTY INTELLECTUAL PROPERTY
  * RIGHTS ARE DISCLAIMED TO THE FULLEST EXTENT PERMITTED BY LAW. IN NO EVENT 
  * SHALL STMICROELECTRONICS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
  * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
  * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, 
  * OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF 
  * LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING 
  * NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
  * EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
  *
  ******************************************************************************
  @endverbatim

@par Application Description

Use of the USB device application based on the Mass Storage Class (MSC).

This is a typical application on how to use the STM32F7xx USB OTG Device peripheral to communicate with a PC
Host using the Bulk Only Transfer (BOT) and Small Computer System Interface (SCSI) transparent commands, 
while the microSD card is used as storage media. The STM32 MCU is enumerated as a MSC device using the 
native PC Host MSC driver to which the STM32F769I-Discovery board is connected.

At the beginning of the main program the HAL_Init() function is called to reset all the peripherals,
initialize the Flash interface and the systick. The user is provided with the SystemClock_Config()
function to configure the system clock (SYSCLK) to run at 216 MHz. The Full Speed (FS) USB module uses
internally a 48-MHz clock which is coming from a specific output of two PLLs: main PLL or PLL SAI.
In the High Speed (HS) mode the USB clock (60 MHz) is driven by the ULPI.

When the application is started, the user has just to plug the USB cable into a PC host and the device 
is automatically detected. A new removable drive appears in the system window and write/read/format 
operations can be performed as with any other removable drive.

@note Care must be taken when using HAL_Delay(), this function provides accurate delay (in milliseconds)
      based on variable incremented in SysTick ISR. This implies that if HAL_Delay() is called from
      a peripheral ISR process, then the SysTick interrupt must have higher priority (numerically lower)
      than the peripheral interrupt. Otherwise the caller ISR process will be blocked.
      To change the SysTick interrupt priority you have to use HAL_NVIC_SetPriority() function.
      
@note The application needs to ensure that the SysTick time base is always set to 1 millisecond
      to have correct HAL operation.
      
For more details about the STM32Cube USB Device library, please refer to UM1734 
"STM32Cube USB Device library".


@par Keywords

Connectivity, USB Device, MSC, Mass Storage, Full Speed, High Speed, BOT, SCSI, SD Card, Removable drive,
Write, Read, Format

@Note�If the user code size exceeds the DTCM-RAM size or starts from internal cacheable memories (SRAM1 and SRAM2),that is shared between several processors,
 �����then it is highly recommended to enable the CPU cache and maintain its coherence at application level.
������The address and the size of cacheable buffers (shared between CPU and other masters)  must be properly updated to be aligned to cache line size (32 bytes).

@Note It is recommended to enable the cache and maintain its coherence, but depending on the use case
����� It is also possible to configure the MPU as "Write through", to guarantee the write access coherence.
������In that case, the MPU must be configured as Cacheable/Bufferable/Not Shareable.
������Even though the user must manage the cache coherence for read accesses.
������Please refer to the AN4838 �Managing memory protection unit (MPU) in STM32 MCUs�
������Please refer to the AN4839 �Level 1 cache on STM32F7 Series�

@par Directory contents

  - USB_Device/MSC_Standalone/Src/main.c                  Main program
  - USB_Device/MSC_Standalone/Src/system_stm32f7xx.c      STM32F7xx system clock configuration file
  - USB_Device/MSC_Standalone/Src/stm32f7xx_it.c          Interrupt handlers
  - USB_Device/MSC_Standalone/Src/usbd_conf.c             General low level driver configuration
  - USB_Device/MSC_Standalone/Src/usbd_desc.c             USB device MSC descriptor
  - USB_Device/MSC_Standalone/Src/ubsd_storage.c          Media Interface Layer
  - USB_Device/MSC_Standalone/Inc/main.h                  Main program header file
  - USB_Device/MSC_Standalone/Inc/stm32f7xx_it.h          Interrupt handlers header file
  - USB_Device/MSC_Standalone/Inc/stm32f7xx_hal_conf.h    HAL configuration file
  - USB_Device/MSC_Standalone/Inc/usbd_conf.h             USB device driver Configuration file
  - USB_Device/MSC_Standalone/Inc/usbd_desc.h             USB device MSC descriptor header file
  - USB_Device/MSC_Standalone/Inc/ubsd_storage.h          Media Interface Layer header file   

	
@par Hardware and Software environment

  - This application runs on STM32F767xx/STM32F769xx/STM32F777xx/STM32F779xx devices.
    
  - This application has been tested with STMicroelectronics STM32F769I-Discovery
    boards and can be easily tailored to any other supported device 
    and development board.

  - STM32F769I-Discovery Set-up
    - Insert a microSD card into the STM32F769I-Discovery uSD slot (CN5)
    - Connect the STM32F769I-Discovery board to the PC through 'USB micro A-Male 
      to A-Male' cable to the connector:
      - CN15 : to use USB High Speed (HS) 

@par How to use it ?

In order to make the program work, you must do the following :
 - Open your preferred toolchain 
 - Rebuild all files and load your image into target memory
 - In the workspace toolbar select the project configuration:
   - STM32F769I-Discovery-HS: to configure the project for STM32F7xx devices using USB OTG HS peripheral
 - Run the application
 
 * <h3><center>&copy; COPYRIGHT STMicroelectronics</center></h3>
 */
 