from PIL import Image
import st7789

mid = st7789.ST7789(
    width=240, height=240, rotation=0,
    port=1, cs=0, dc=22, rst=27, backlight=19,
    spi_speed_hz=40000000,
)
img = Image.new("RGB", (240, 240), (255, 0, 0))
mid.display(img)
print("done — screen should be solid RED")
