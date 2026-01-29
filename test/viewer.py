#!/usr/bin/env python3
"""
Simple Event Viewer - Connects to the converter and displays events

Uses dv-processing library to receive and visualize events from the converter.

Usage:
    python3 viewer.py
    python3 viewer.py --ip 127.0.0.1 --port 7777
"""

import argparse
import sys

try:
    import dv_processing as dv
    import cv2 as cv
    from datetime import timedelta
except ImportError as e:
    print(f"Error: Missing required library: {e}")
    print("Install with: pip3 install dv-processing opencv-python")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Event stream viewer")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="Converter IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=7777, help="Converter port (default: 7777)")
    args = parser.parse_args()

    print(f"Connecting to {args.ip}:{args.port}...")
    
    try:
        # Connect to the converter
        client = dv.io.NetworkReader(args.ip, args.port)
    except Exception as e:
        print(f"Failed to connect: {e}")
        print("Make sure the converter is running!")
        sys.exit(1)

    # Validate that this client is connected to an event data stream
    if not client.isEventStreamAvailable():
        print("Error: Server does not provide event data!")
        sys.exit(1)

    # Get resolution from server
    resolution = client.getEventResolution()
    print(f"Connected! Resolution: {resolution[0]}x{resolution[1]}")
    print("Press ESC to exit")

    # Initialize the event visualizer
    visualizer = dv.visualization.EventVisualizer(resolution)

    # Create a preview window
    cv.namedWindow("Event Viewer", cv.WINDOW_NORMAL)
    cv.resizeWindow("Event Viewer", 1280, 720)

    # Event stream slicer for synchronized visualization
    slicer = dv.EventStreamSlicer()

    # Callback to show the generated event visualization
    def show_preview(events):
        if events.size() > 0:
            # Generate and display preview image
            frame = visualizer.generateImage(events)
            cv.imshow("Event Viewer", frame)

        # Check for ESC key
        if cv.waitKey(1) == 27:
            print("\nExiting...")
            cv.destroyAllWindows()
            sys.exit(0)

    # Visualize every 10 milliseconds
    slicer.doEveryTimeInterval(timedelta(milliseconds=10), show_preview)

    # Main loop
    frame_count = 0
    try:
        while client.isRunning():
            # Read event data
            events = client.getNextEventBatch()

            # Validate and feed into slicer
            if events is not None:
                slicer.accept(events)
                frame_count += 1
                
                if frame_count % 100 == 0:
                    print(f"Received {frame_count} batches, {events.size()} events in last batch")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        cv.destroyAllWindows()
        print("Viewer closed")


if __name__ == "__main__":
    main()
