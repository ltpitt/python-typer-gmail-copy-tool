import pyautogui
import random
import time

screen_width, screen_height = pyautogui.size()

interval_range_seconds = (50, 100)
duration_range_seconds = (0.3, 0.7)
long_pause_chance = 0.1  # 10% chance of a long pause
long_pause_range_seconds = (30, 60)
small_movement_chance = 0.5  # 50% chance of small movements
small_movement_range = (-10, 10)

def human_like_move(x, y, duration):
    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)

while True:
    # Avoid screen edges by keeping the cursor within 30 pixels of the edge
    x = random.randint(10, screen_width - 30)
    y = random.randint(10, screen_height - 30)

    duration = random.uniform(*duration_range_seconds)
    human_like_move(x, y, duration)

    if random.random() < small_movement_chance:
        small_dx = random.randint(*small_movement_range)
        small_dy = random.randint(*small_movement_range)
        human_like_move(x + small_dx, y + small_dy, duration=random.uniform(0.1, 0.2))

    if random.random() < long_pause_chance:
        pyautogui.keyDown("1")
        pyautogui.keyDown("backspace")
        time.sleep(random.uniform(*long_pause_range_seconds))
    else:
        interval = random.uniform(*interval_range_seconds)
        time.sleep(interval)