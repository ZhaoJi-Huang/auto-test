import time
import math

class ActionAnalyzer:
    """
    全功能状态机：解析 Tap, LongPress, Swipe, Drag
    """
    def __init__(self, width_ratio=1.0, height_ratio=1.0):
        self.ratio_x = width_ratio
        self.ratio_y = height_ratio
        
        # === 阈值定义 ===
        self.MOVE_THRESHOLD = 30       # 移动多少像素才算滑动
        self.LONG_PRESS_TIME = 0.6     # 超过多少秒算长按
        self.DRAG_DURATION = 1.5       # 超过多少秒的滑动算慢速拖拽
        
        self.reset()

    def reset(self):
        self.start_x = -1
        self.start_y = -1
        self.last_x = -1
        self.last_y = -1
        self.start_time = 0
        self.is_pressing = False
        self.max_move_distance = 0 # 记录按下过程中最大的移动距离（用于防抖）

    def process_line(self, event_dict):
        etype = event_dict['type']
        ecode = event_dict['code']
        evalue = event_dict['value']

        # ABS_MT_TRACKING_ID (0x39 / 57)
        if ecode == 57: 
            if evalue != 0xffffffff: 
                # Finger Down
                self.is_pressing = True
                self.start_time = time.time()
                return None
            else:
                # Finger Up - 结算动作
                if self.is_pressing:
                    result = self.generate_command()
                    self.reset()
                    return result

        # 记录坐标变化
        if self.is_pressing:
            if ecode == 53: # X轴
                screen_x = int(evalue * self.ratio_x)
                if self.start_x == -1: self.start_x = screen_x
                self.last_x = screen_x
            elif ecode == 54: # Y轴
                screen_y = int(evalue * self.ratio_y)
                if self.start_y == -1: self.start_y = screen_y
                self.last_y = screen_y
            
            # 计算当前偏离起点的距离，更新 max_move_distance
            if self.start_x != -1 and self.last_x != -1:
                curr_dist = math.sqrt((self.last_x - self.start_x)**2 + (self.last_y - self.start_y)**2)
                if curr_dist > self.max_move_distance:
                    self.max_move_distance = curr_dist
        
        return None

    def generate_command(self):
        # 计算持续时间 (ms)
        duration_sec = time.time() - self.start_time
        duration_ms = int(duration_sec * 1000)
        
        # 判断是“静止”还是“移动”
        # 这里使用 max_move_distance 而不是终点与起点的距离
        # 原因是：如果用户滑出去又滑回来（画了个圈回到原点），这应该算 Swipe 而不是 Tap
        is_static = self.max_move_distance < self.MOVE_THRESHOLD
        
        # === 逻辑分支 ===
        
        # 1. 静止操作 (Tap 或 Long Press)
        if is_static:
            if duration_sec < self.LONG_PRESS_TIME:
                # [点击]
                return {
                    "type": "tap",
                    "cmd": f"input tap {self.start_x} {self.start_y}",
                    "desc": f"点击 ({self.start_x}, {self.start_y})",
                    "duration_ms": duration_ms
                }
            else:
                # [长按] 
                # ADB 实现长按通常是用 swipe 原地滑动 + 耗时
                return {
                    "type": "long_press",
                    "cmd": f"input swipe {self.start_x} {self.start_y} {self.start_x} {self.start_y} {duration_ms}",
                    "desc": f"长按 ({self.start_x}, {self.start_y}) 持续 {duration_ms}ms",
                    "duration_ms": duration_ms
                }
        
        # 2. 移动操作 (Swipe 或 Drag)
        else:
            # ADB 中 swipe 和 drag 指令是一样的，区别主要在于持续时间
            # 这里的区分主要是为了语义记录，方便后续可能的优化
            action_type = "swipe"
            action_desc = "滑动"
            
            if duration_sec > self.DRAG_DURATION:
                action_type = "drag"
                action_desc = "慢速拖拽"

            return {
                "type": action_type,
                # 注意：Swipe操作 ADB 指令必须包含时长，否则默认为极快滑动
                "cmd": f"input swipe {self.start_x} {self.start_y} {self.last_x} {self.last_y} {duration_ms}",
                "desc": f"{action_desc} ({self.start_x},{self.start_y}) -> ({self.last_x},{self.last_y}) 耗时 {duration_ms}ms",
                "duration_ms": duration_ms
            }