This implements the **Generic USB Display** on a microcontroller.

I wanted a development board that had an LCD and a USB HighSpeed connector and ended up with a [STM32F769I-DISCO](https://www.st.com/resource/en/user_manual/dm00276557-discovery-kit-with-stm32f769ni-mcu-stmicroelectronics.pdf).

I installed the STM32CubeIDE and merged 2 example projects: Projects\STM32F769I-Discovery\Applications\USB_Device and Projects\STM32F769I-Discovery\Applications\Display.

My main problem was that I got garbage on the display which turned out to be due to lcd controller fifo underuns.
I was exceeding the memory bandwidth. Some cache flag incantations from Projects\STM32F769I-Discovery\Demonstrations\STemWin magically cleared it up.
Now there's only some occasional garbling...

Movie: https://youtu.be/BjvqcGssO3w

Since memory bandwidth seem to be a problem, I didn't even try to implement compression since that would put further pressure on the matrix.

One full frame is split into 12 parts to avoid fifo underruns, didn't test other values.

tools/monitor.py results after running modetest -v:
```
Flush: 800x40+0+0 length=64000 (  2.2 + 1.9 =   4.2 ms)
Flush: 800x40+0+40 length=64000 (  2.2 + 1.9 =   4.1 ms)
Flush: 800x40+0+80 length=64000 (  2.1 + 1.9 =   4.1 ms)
Flush: 800x40+0+120 length=64000 (  2.2 + 1.9 =   4.2 ms)
Flush: 800x40+0+160 length=64000 (  2.2 + 1.9 =   4.2 ms)
Flush: 800x40+0+200 length=64000 (  2.2 + 1.9 =   4.2 ms)
Flush: 800x40+0+240 length=64000 (  1.4 + 1.9 =   3.4 ms)
Flush: 800x40+0+280 length=64000 (  2.2 + 1.9 =   4.2 ms)
Flush: 800x40+0+320 length=64000 (  1.5 + 1.9 =   3.5 ms)
Flush: 800x40+0+360 length=64000 (  2.2 + 1.9 =   4.3 ms)
Flush: 800x40+0+400 length=64000 (  1.3 + 1.9 =   3.4 ms)
Flush: 800x40+0+440 length=64000 (  2.3 + 1.9 =   4.3 ms)
^C
Statistics:
    Rects:
        800x40: 1.8 < 5.0 ms < 13.0 (2150)
        8x16: 0.3 < 1.0 ms < 1.3 (11)
    Full:
        800x480: 4.1 < 9.4 ms < 72.6 (179)
    Totals (2161):
        time: 13 seconds
        compression: 0.0
        throughput: 9.7 MB/s
        fps=13.2
```

I don't plan to pursue this any further, it was just a hack to give hints to anyone wanting to make a USB display.
