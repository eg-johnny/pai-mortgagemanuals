import os
import time
import hashlib
import requests
from pytube import YouTube
from tqdm import tqdm

from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Azure Speech-to-Text imports (if fallback is needed)
# from azure.cognitiveservices.speech import SpeechConfig, SpeechRecognizer, AudioConfig

# ------------------------------ #
#        Load Environment        #
# ------------------------------ #
load_dotenv()

# Azure Speech service details (only needed if using Azure Speech fallback)
# speech_key = os.getenv('AZURE_SPEECH_KEY')
# service_region = os.getenv('AZURE_SERVICE_REGION')

# ------------------------------ #
#  Video & Transcript Functions  #
# ------------------------------ #

def download_audio(video_url, output_path):
    """
    Download the first stream from the given YouTube video_url as 'audio.mp4'
    and store it in output_path.
    """
    yt = YouTube(video_url)
    # Download the first available stream as audio (mp4 format).
    yt.streams.first().download(output_path=output_path, filename='audio.mp4')

def transcribe_audio(audio_path):
    """
    Transcribe audio using Azure Speech-to-Text SDK.
    """
    # speech_config = SpeechConfig(subscription=speech_key, region=service_region)
    # audio_config = AudioConfig(filename=audio_path)
    # recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    done = False
    transcript = []

    def stop_cb(evt):
        nonlocal done
        done = True

    def recognized_cb(evt):
        transcript.append(evt.result.text)

    recognizer.recognized.connect(recognized_cb)
    recognizer.session_stopped.connect(stop_cb)
    recognizer.canceled.connect(stop_cb)

    recognizer.start_continuous_recognition()
    while not done:
        time.sleep(0.5)

    recognizer.stop_continuous_recognition()
    return ' '.join(transcript)

def get_video_description(video_url):
    """
    Retrieve video description using PyTube.
    """
    yt = YouTube(video_url)
    return yt.description

def get_transcript(video_id, video_url):
    """
    Attempt to fetch transcript using the YouTubeTranscriptApi.
    If that fails, fall back to Azure Speech-to-Text by downloading audio.
    """
    try:
        # Try to fetch transcript using YouTubeTranscriptApi
        transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
        # Combine transcript text
        transcript_text = "\n".join([item['text'] for item in transcript_data])
        return transcript_text
    except Exception as e:
        print(f"Failed to fetch transcript using YouTubeTranscriptApi: {e}")
        print("Attempting to extract audio and use Azure Speech-to-Text...")

    #     try:
    #         # Download audio from video
    #         download_audio(video_url, '/tmp')
    #         # Transcribe audio
    #         transcript_text = transcribe_audio('/tmp/audio.mp4')
    #         return transcript_text
    #     except Exception as e:
    #         print(f"Failed to transcribe audio using Azure Speech-to-Text: {e}")
    #         return f"An error occurred: {e}"

def get_videos_from_channel(channel_url):
    """
    Scroll through a YouTube channel page using Selenium (headless),
    gather video IDs and titles, and return them as a list of tuples (video_id, title).
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = None
    videos = []

    try:
        driver = webdriver.Chrome(options=options, service=Service(ChromeDriverManager().install()))
        driver.get(channel_url)

        last_height = driver.execute_script("return document.documentElement.scrollHeight")

        while True:
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")

            # Wait for new content to load
            time.sleep(2)  # Adjust if needed

            # Calculate new scroll height
            new_height = driver.execute_script("return document.documentElement.scrollHeight")

            # Break the loop if no new content loaded
            if new_height == last_height:
                break
            last_height = new_height

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "contents")))

        user_data = driver.find_elements(By.XPATH, '//*[@id="video-title-link"]')

        for element in user_data:
            href = element.get_attribute('href')
            title = element.get_attribute('title')
            if href and "watch?v=" in href:
                v_id = href.split('v=')[1]
                videos.append((v_id, title))
    finally:
        if driver is not None:
            driver.quit()

    return videos

def save_transcript_locally(transcript, description, title):
    """
    Save the combined description and transcript text to ../data/YouTube_Transcripts/<title>.txt.
    Creates the directory if it doesn't exist.
    """
    # Ensure the directory exists
    save_directory = os.path.join("..", "data", "YouTube_Transcripts")
    os.makedirs(save_directory, exist_ok=True)

    # Construct the file path
    # Sanitize the title if needed to remove forbidden characters in filenames
    sanitized_title = "".join(char for char in title if char.isalnum() or char in " ._-")
    filename = f"{sanitized_title}.txt"
    file_path = os.path.join(save_directory, filename)

    # Combine and write content
    combined_content = f"Description:\n{description}\n\nTranscript:\n{transcript}"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(combined_content)

    print(f"Transcript saved locally as: {file_path}")

# ------------------------------ #
#           Main Script          #
# ------------------------------ #

if __name__ == "__main__":
    # Prompt the user for the YouTube channel URL
    channel_url = input("Please enter URL to the YouTube channel videos page: ")

    # Get the list of videos
    print(f"Gathering videos from: {channel_url}")
    videos = get_videos_from_channel(channel_url)
    print(f"Found {len(videos)} videos.")

    # Process each video with a progress bar
    for video_id, title in tqdm(videos, desc="Transcribing videos", unit="video"):
        video_url = f'https://www.youtube.com/watch?v={video_id}'
        transcript = get_transcript(video_id, video_url)
        description = get_video_description(video_url)
        save_transcript_locally(transcript, description, title)

    print("\nAll done!")
