import pyautogui
import cv2
import numpy as np
import tkinter as tk
from PIL import ImageGrab
import time
from mouseLib import *

def detectImage(image_path, confidence=0.8):
    """
    Detect the given image on the screen.

    Args:
        image_path (str): The path to the image to detect.
        confidence (float): The confidence threshold for matching. Default is 0.8.

    Returns:
        tuple: The center (x, y) coordinates of the detected image, or None if not found.
    """
    try:
        # Capture a screenshot of the screen
        screenshot = pyautogui.screenshot()
        screen_array = np.array(screenshot)
        screen_gray = cv2.cvtColor(screen_array, cv2.COLOR_BGR2GRAY)

        # Load the target image
        template = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            print("Error: Could not load the image. Please check the image path.")
            return None

        # Match the template with the screen
        result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # Check if the detected match exceeds the confidence threshold
        if max_val >= confidence:
            template_height, template_width = template.shape
            center_x = max_loc[0] + template_width // 2
            center_y = max_loc[1] + template_height // 2
            return (center_x, center_y)

        print("Image not found on the screen.")
        return None

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def waitForImage(image_path, confidence=0.8, timeout=30, interval=1):
    """
    Wait for an image to appear on the screen.

    Args:
        image_path (str): The path to the image to detect.
        confidence (float): The confidence threshold for matching. Default is 0.8.
        timeout (int): The maximum time (in seconds) to wait for the image. Default is 30 seconds.
        interval (int): The time (in seconds) between each detection attempt. Default is 1 second.

    Returns:
        tuple: The center (x, y) coordinates of the detected image, or None if not found.
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        center_coordinates = detectImage(image_path, confidence=confidence)
        if center_coordinates is not None:
            print(f"Image found at: {center_coordinates}")
            return center_coordinates

        time.sleep(interval)  # Wait before trying again

    print("Timed out waiting for the image.")
    return None

def clickOnImage(center_coordinates, click_type="left", double=False, smoothness=0.1, steps=50):
    """
    Click on the specified part of the screen with smooth mouse movement.

    Args:
        center_coordinates (tuple): The (x, y) coordinates to click.
        click_type (str): Type of click: "left" or "right". Default is "left".
        double (bool): Whether to perform a double-click. Default is False.
        smoothness (float): The time (in seconds) it takes to move the mouse to the location. Default is 0.1 seconds.
        steps (int): Number of intermediate steps for the movement. Default is 50.        
    """
    try:
        if center_coordinates is not None:
            moveMouseClick(center_coordinates[0], center_coordinates[1], click_type, double, smoothness, steps)
            print(f"Clicked at: {center_coordinates}")
        else:
            print("Invalid coordinates. Cannot perform the click.")
    except Exception as e:
        print(f"An error occurred while clicking: {e}")

def captureScreenRegion(region, output_path):
    """
    Capture a specific region of the screen and save it as a PNG file.

    Args:
        region (tuple): A tuple specifying the region to capture in the format (x, y, width, height).
        output_path (str): The file path to save the captured image.

    Returns:
        bool: True if the capture was successful, False otherwise.
    """
    try:
        # Capture the specified region
        screenshot = pyautogui.screenshot(region=region)
        # Save the captured region as a PNG file
        screenshot.save(output_path)
        print(f"Region captured and saved to {output_path}")
        return True
    except Exception as e:
        print(f"An error occurred while capturing the screen region: {e}")
        return False

def selectScreenRegion():
    """
    Allow the user to select a part of the screen using the mouse and visually draw a rectangle.
    Returns the selected region as a tuple: (x, y, width, height).
    """
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.3)  # Make the window transparent
    root.title("Select a region")

    canvas = tk.Canvas(root, cursor="cross", bg="gray", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    start_x = start_y = None
    rect_id = None
    selected_region = None

    def on_mouse_down(event):
        nonlocal start_x, start_y, rect_id
        start_x, start_y = event.x, event.y
        rect_id = canvas.create_rectangle(start_x, start_y, start_x, start_y, outline="red", width=2)

    def on_mouse_drag(event):
        nonlocal rect_id
        if rect_id:
            canvas.coords(rect_id, start_x, start_y, event.x, event.y)

    def on_mouse_up(event):
        nonlocal selected_region
        end_x, end_y = event.x, event.y
        x1, y1 = min(start_x, end_x), min(start_y, end_y)
        x2, y2 = max(start_x, end_x), max(start_y, end_y)
        selected_region = (x1, y1, x2 - x1, y2 - y1)
        root.quit()

    canvas.bind("<Button-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_drag)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)

    root.mainloop()
    root.destroy()

    return selected_region

if __name__ == "__main__":
    # Example: Capture a region of the screen and save it as an image
    region = selectScreenRegion()
    if region:
        output_path = "captured_region.png"
        captureScreenRegion(region, output_path)
    else:
        print("No region selected.")