from pynput import mouse, keyboard
from pynput.mouse import Button, Controller
import time
import json

is_recording = False
ctrl_pressed = False  # Track the state of the Ctrl key

def moveMouse(target_x, target_y, duration=0.5, steps=50):
    """
    Move the mouse smoothly to the specified position.

    Args:
        target_x (int): The target x-coordinate.
        target_y (int): The target y-coordinate.
        duration (float): Total time (in seconds) to move the mouse. Default is 0.5 seconds.
        steps (int): Number of intermediate steps for the movement. Default is 50.
    """
    mouse = Controller()
    start_x, start_y = mouse.position
    step_duration = duration / steps

    for step in range(1, steps + 1):
        # Interpolate position
        current_x = start_x + (target_x - start_x) * step / steps
        current_y = start_y + (target_y - start_y) * step / steps
        mouse.position = (int(current_x), int(current_y))

        # Wait for the next step
        time.sleep(step_duration)

    print(f"Mouse moved to ({target_x}, {target_y})")

def moveMouseClick(target_x, target_y, click_type="left", double=False, duration=0.5, steps=50):
    """
    Move the mouse smoothly to the specified position and perform a click.

    Args:
        target_x (int): The target x-coordinate.
        target_y (int): The target y-coordinate.
        click_type (str): Type of click: "left" or "right". Default is "left".
        double (bool): Whether to perform a double-click. Default is False.
        duration (float): Total time (in seconds) to move the mouse. Default is 0.5 seconds.
        steps (int): Number of intermediate steps for the movement. Default is 50.
    """
    # Move the mouse to the target position
    moveMouse(target_x, target_y, duration, steps)

    # Perform the specified click
    mouse = Controller()

    if click_type == "left":
        if double:
            mouse.click(Button.left, 2)  # Double left-click
        else:
            mouse.click(Button.left)  # Single left-click
    elif click_type == "right":
        if double:
            mouse.click(Button.right, 2)  # Double right-click
        else:
            mouse.click(Button.right)  # Single right-click
    else:
        print(f"Invalid click type: {click_type}")
        return

    print(f"Mouse moved to ({target_x}, {target_y}) and performed a {'double' if double else 'single'} {click_type}-click.")

def recordMouseEvents(output_file):
    """
    Record mouse events and save them to a file, filtering unnecessary move events.

    Args:
        output_file (str): The path to the file where mouse events will be saved.
    """
    global is_recording, ctrl_pressed
    events = []
    start_time = time.time()
    last_move = {"x": None, "y": None}  # Track last recorded move

    def on_move(x, y):
        if is_recording:
            # Record only if moved significantly or if this is the first move
            if last_move["x"] is None or abs(x - last_move["x"]) > 2 or abs(y - last_move["y"]) > 2:
                events.append({"type": "move", "time": time.time() - start_time, "x": x, "y": y})
                last_move["x"], last_move["y"] = x, y

    def on_click(x, y, button, pressed):
        if is_recording:
            events.append({
                "type": "click",
                "time": time.time() - start_time,
                "x": x,
                "y": y,
                "button": str(button),
                "pressed": pressed,
            })

    def on_scroll(x, y, dx, dy):
        if is_recording:
            events.append({
                "type": "scroll",
                "time": time.time() - start_time,
                "x": x,
                "y": y,
                "dx": dx,
                "dy": dy,
            })

    def on_key_press(key):
        global is_recording, ctrl_pressed
        try:
            if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                ctrl_pressed = True
            elif key == keyboard.Key.f1 and ctrl_pressed:
                is_recording = not is_recording
                if is_recording:
                    print("Recording started.")
                else:
                    print("Recording stopped.")
                    # Save events and stop both listeners
                    with open(output_file, "w") as f:
                        json.dump(events, f)
                    print(f"Mouse events recorded and saved to {output_file}")
                    return False
        except AttributeError:
            pass

    def on_key_release(key):
        global ctrl_pressed
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            ctrl_pressed = False

    print("Press 'Ctrl+F1' to start/stop recording.")
    
    # Start the mouse and keyboard listeners
    with mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll) as mouse_listener, \
            keyboard.Listener(on_press=on_key_press, on_release=on_key_release) as keyboard_listener:
        keyboard_listener.join()
        mouse_listener.stop()

def replayMouseEvents(input_file):
    """
    Replay mouse events from a file using pynput for faster performance.

    Args:
        input_file (str): The path to the file containing recorded mouse events.
    """
    # Load recorded events
    with open(input_file, "r") as f:
        events = json.load(f)

    mouse = Controller()
    replay_start_time = time.time()

    for event in events:
        # Synchronize timing
        target_time = replay_start_time + event["time"]
        while time.time() < target_time:
            pass  # Busy-wait to synchronize timing (minimize overhead)

        # Handle move events
        if event["type"] == "move":
            mouse.position = (event["x"], event["y"])

        # Handle click events
        elif event["type"] == "click":
            if event["pressed"]:
                if event["button"] == "Button.left":
                    mouse.press(Button.left)
                elif event["button"] == "Button.right":
                    mouse.press(Button.right)
            else:
                if event["button"] == "Button.left":
                    mouse.release(Button.left)
                elif event["button"] == "Button.right":
                    mouse.release(Button.right)

        # Handle scroll events
        elif event["type"] == "scroll":
            mouse.scroll(0, event["dy"])

    print("Mouse events replayed.")


# Example usage
if __name__ == "__main__":
    print("Choose an option:")
    print("1. Record mouse events")
    print("2. Replay mouse events")

    choice = input("Enter your choice (1/2): ").strip()
    if choice == "1":
        output_file = "mouse_events.json"
        recordMouseEvents(output_file)
    elif choice == "2":
        input_file = "mouse_events.json"
        replayMouseEvents(input_file)
    else:
        print("Invalid choice.")
