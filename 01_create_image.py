import cv2
import numpy as np

# 创建一张 300x300 的黑色背景图片（3通道 BGR，全 0 即黑色）
img = np.zeros((300, 300, 3), dtype=np.uint8)

# 将第3行与第10行（从1开始计数，对应索引 2 和 9）整行修改为白色
img[102, :] = (255, 255, 255)
img[109, :] = (255, 255, 255)

# 打印验证：第2行应仍为黑色，第3、10行应为白色
print("第2行 [0,0,0] 像素值:", img[1, 0])
print("第3行 [0,0,0] 像素值:", img[2, 0])
print("第10行[0,0,0] 像素值:", img[9, 0])

# 保存图片
cv2.imwrite("01_create_image.png", img)

# 显示原始效果
cv2.imshow("300x300: row 3 & row 10 white", img)

# 放大3倍显示，便于观察白色行效果
cv2.imshow("zoom x3", cv2.resize(img, (900, 900), interpolation=cv2.INTER_NEAREST))

cv2.waitKey(0)
cv2.destroyAllWindows()
