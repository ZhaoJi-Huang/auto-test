import cv2

def show_capture(device_index=0):
    cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("❌ 无法打开采集卡")
        return

    print("✅ 采集卡已打开，按 q 退出")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ 读取画面失败")
            break

        cv2.imshow("TV Capture", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    show_capture(1)  # 如果看不到，改成 1 / 2 / 3