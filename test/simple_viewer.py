#!/usr/bin/env python3
"""
Simple Event Viewer - No dv-processing required!

This viewer connects to the fake camera directly and visualizes the 2-bit packed frames.
It bypasses the converter entirely for testing/visualization purposes.

Usage:
    python3 simple_viewer.py
"""

import socket
import numpy as np
import cv2
import signal
import sys

# Settings - must match FPGA/fake camera
WIDTH = 1280
HEIGHT = 720
FRAME_SIZE = (WIDTH * HEIGHT + 3) // 4
PORT = 6000  # Same as fake camera sends to

running = True

def signal_handler(sig, frame):
    global running
    print("\nExiting...")
    running = False

signal.signal(signal.SIGINT, signal_handler)


def unpack_frame(data):
    """Unpack 2-bit packed frame to visualization image"""
    # Create output image (grayscale)
    img = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    img[:] = 128  # Gray background (no events)
    
    pixel_idx = 0
    for byte_idx, byte_val in enumerate(data):
        if byte_val == 0:
            pixel_idx += 4
            continue
            
        for shift in [6, 4, 2, 0]:
            if pixel_idx >= WIDTH * HEIGHT:
                break
            
            pixel = (byte_val >> shift) & 0x03
            
            if pixel != 0:
                y = pixel_idx // WIDTH
                x = pixel_idx % WIDTH
                
                if pixel == 0x01:  # Positive polarity (p=1)
                    img[y, x] = 255  # White
                elif pixel == 0x02:  # Negative polarity (p=0)
                    img[y, x] = 0    # Black
            
            pixel_idx += 1
    
    return img


def main():
    global running
    
    print("=" * 60)
    print("Simple Event Viewer")
    print("=" * 60)
    print(f"Resolution: {WIDTH}x{HEIGHT}")
    print(f"Frame size: {FRAME_SIZE} bytes")
    print(f"Listening on port: {PORT}")
    print("=" * 60)
    print()
    print("This viewer acts as a TCP SERVER.")
    print("Run the fake camera to send frames here.")
    print()
    print("Press 'q' or ESC to quit")
    print()
    
    # Create TCP server socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)
    
    try:
        server.bind(("0.0.0.0", PORT))
        server.listen(1)
        print(f"Waiting for connection on port {PORT}...")
        
        client = None
        while running and client is None:
            try:
                client, addr = server.accept()
                print(f"Connected: {addr}")
                client.settimeout(1.0)
            except socket.timeout:
                continue
        
        if client is None:
            return
        
        # Create window
        cv2.namedWindow("Event Viewer", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Event Viewer", 1280, 720)
        
        frame_count = 0
        buffer = b""
        
        while running:
            try:
                # Receive data
                chunk = client.recv(65536)
                if not chunk:
                    print("Connection closed")
                    break
                
                buffer += chunk
                
                # Process complete frames
                while len(buffer) >= FRAME_SIZE:
                    frame_data = buffer[:FRAME_SIZE]
                    buffer = buffer[FRAME_SIZE:]
                    
                    # Unpack and display
                    img = unpack_frame(frame_data)
                    
                    # Add frame counter
                    cv2.putText(img, f"Frame: {frame_count}", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
                    
                    cv2.imshow("Event Viewer", img)
                    frame_count += 1
                    
                    if frame_count % 100 == 0:
                        print(f"Frames received: {frame_count}")
                
                # Check for key press
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:  # q or ESC
                    break
                    
            except socket.timeout:
                # Check for key press even when no data
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    break
                continue
            except Exception as e:
                print(f"Error: {e}")
                break
        
        client.close()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        server.close()
        cv2.destroyAllWindows()
        print(f"Total frames: {frame_count}")


if __name__ == "__main__":
    main()
