import cv2
import numpy as np

# ===== 滑块回调（空函数即可，逻辑在主循环里取值） =====
def nothing(x):
    pass

# ===== 创建 HSV 调节窗口与滑块 =====
cv2.namedWindow("HSV", cv2.WINDOW_NORMAL)
cv2.resizeWindow("HSV", 500, 360)

# HSV 范围：H 0-179, S 0-255, V 0-255（OpenCV 约定）
cv2.createTrackbar("H_min", "HSV", 0,   179, nothing)
cv2.createTrackbar("H_max", "HSV", 179, 179, nothing)
cv2.createTrackbar("S_min", "HSV", 0,   255, nothing)
cv2.createTrackbar("S_max", "HSV", 255, 255, nothing)
cv2.createTrackbar("V_min", "HSV", 0,   255, nothing)
cv2.createTrackbar("V_max", "HSV", 255, 255, nothing)

# ===== 创建形态学操作窗口（腐蚀/膨胀） =====
cv2.namedWindow("Morph", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Morph", 400, 200)
cv2.createTrackbar("Erode",  "Morph", 1, 20, nothing)   # 腐蚀迭代次数
cv2.createTrackbar("Dilate", "Morph", 1, 20, nothing)   # 膨胀迭代次数

# ===== 打开摄像头 =====
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("无法打开摄像头，请检查设备或索引")
    exit(0)

print("按 ESC 退出，按 s 保存当前 HSV 参数")

while True:
    ret, frame = cap.read()
    if not ret:
        print("读取帧失败")
        break

    # ----- 读取滑块参数 -----
    h_min = cv2.getTrackbarPos("H_min", "HSV")
    h_max = cv2.getTrackbarPos("H_max", "HSV")
    s_min = cv2.getTrackbarPos("S_min", "HSV")
    s_max = cv2.getTrackbarPos("S_max", "HSV")
    v_min = cv2.getTrackbarPos("V_min", "HSV")
    v_max = cv2.getTrackbarPos("V_max", "HSV")
    erode_n  = cv2.getTrackbarPos("Erode",  "Morph")
    dilate_n = cv2.getTrackbarPos("Dilate", "Morph")

    # ----- BGR -> HSV 并生成 MASK -----
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array([h_min, s_min, v_min])
    upper = np.array([h_max, s_max, v_max])
    mask = cv2.inRange(hsv, lower, upper)   # MASK: 白色为命中区域

    # ----- 腐蚀 / 膨胀 -----
    kernel = np.ones((5, 5), np.uint8)
    # 腐蚀：去掉小白点噪声
    if erode_n > 0:
        mask = cv2.erode(mask, kernel, iterations=erode_n)
    # 膨胀：补回腐蚀掉的主体区域，连通大块
    if dilate_n > 0:
        mask = cv2.dilate(mask, kernel, iterations=dilate_n)

    # ----- 结果图：原图按 MASK 保留命中区域 -----
    result = cv2.bitwise_and(frame, frame, mask=mask)

    # ----- 三图同屏显示 -----
    # MASK 为单通道，转 BGR 方便和原图并排
    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    combined = np.hstack((frame, mask_bgr, result))

    cv2.imshow("Origin | MASK | Result", combined)

    key = cv2.waitKey(1) & 0xFF
    if key == 27:        # ESC
        break
    elif key == ord('s'):  # 保存当前 HSV 参数
        print(f"HSV: H[{h_min}-{h_max}] S[{s_min}-{s_max}] V[{v_min}-{v_max}] "
              f"Erode={erode_n} Dilate={dilate_n}")

cap.release()
cv2.destroyAllWindows()
