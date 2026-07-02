# Musiqueue
A lightweight desktop YouTube queue player built with Python.

Instead of autoplay deciding what plays next, MusiQueue lets you build your own queue. Search for songs, add them to the list, and they'll play one after another in the exact order you added them.

Features
🎵 Search songs directly from YouTube
📋 Queue multiple songs at once
▶ Automatic playback in queue order
⏭ Skip the current song anytime
🎨 Modern neon-themed interface using CustomTkinter
🚫 Prevents YouTube autoplay from taking over the queue
⚡ Live "Now Playing" status updates
Built With
Python
CustomTkinter
Selenium
WebDriver Manager
Installation

Clone the repository:

git clone https://github.com/yourusername/musiqueue.git
cd musiqueue

Install dependencies:

pip install -r requirements.txt

Run the application:

python main.py
Usage
Launch the application.
Type one or more song names (comma-separated if adding multiple).
Press Add.
The first song starts automatically.
Use Skip to move to the next song in the queue.
Notes
Google Chrome must be installed.
A stable internet connection is required.
Playback is performed through YouTube using Selenium automation.


