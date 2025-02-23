import time
from youtube_transcript_api import YouTubeTranscriptApi
import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import hashlib
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from azure.cognitiveservices.speech import SpeechConfig, SpeechRecognizer, AudioConfig
from pytube import YouTube

# Load environment variables
load_dotenv()

# Azure storage account details
connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
container_name = os.getenv('AZURE_STORAGE_CONTAINER')

# Initialize BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

# Azure Speech service details
speech_key = os.getenv('AZURE_SPEECH_KEY')
service_region = os.getenv('AZURE_SERVICE_REGION')

# Function to download video audio
def download_audio(video_url, output_path):
    #YouTube(video_url).streams.first().download()
    yt = YouTube(video_url)
    yt.streams.first().download(output_path=output_path, filename='audio.mp4')

# Function to transcribe audio using Azure Speech-to-Text
def transcribe_audio(audio_path):
    speech_config = SpeechConfig(subscription=speech_key, region=service_region)
    audio_config = AudioConfig(filename=audio_path)
    recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

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

# Function to get video description
def get_video_description(video_url):
    yt = YouTube(video_url)
    return yt.description

# Function to get video transcript
def get_transcript(video_id, video_url):
    try:
        # Try to fetch transcript using YouTubeTranscriptApi
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Combine transcript text
        transcript_text = "\n".join([item['text'] for item in transcript])
        
        return transcript_text
    
    except Exception as e:
        print(f"Failed to fetch transcript using YouTubeTranscriptApi: {e}")
        print("Attempting to extract audio and use Azure Speech-to-Text...")
        
        try:
            # Download audio from video
            download_audio(video_url, '/tmp')
            
            # Transcribe audio
            transcript = transcribe_audio('/tmp/audio.mp4')
            
            return transcript
        
        except Exception as e:
            print(f"Failed to transcribe audio using Azure Speech-to-Text: {e}")
            return f"An error occurred: {e}"

# Function to calculate MD5 hash
def calculate_md5(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

# Function to save transcript to Azure Blob Storage
def save_transcript_to_blob(transcript, description, filename, source_url):
    try:
        combined_content = f"Description:\n{description}\n\nTranscript:\n{transcript}"
        md5_hash = calculate_md5(combined_content)
        blob_client = container_client.get_blob_client(blob=filename)
        
        # Check if blob exists and compare MD5 hash
        if blob_client.exists():
            blob_properties = blob_client.get_blob_properties()
            existing_md5 = blob_properties.metadata.get('MD5')
            if existing_md5 == md5_hash:
                print(f"Transcript for {filename} has not changed. Skipping upload.")
                return
        
        blob_client.upload_blob(combined_content, overwrite=True, metadata={
            'IsDeleted': 'false',
            'MD5': md5_hash,
            'sourceURL': source_url,
            'content_type': 'video transcript'
        })
        print(f"Transcript successfully saved to {filename} in Azure Blob Storage")
    except Exception as e:
        print(f"Failed to save transcript: {e}")

def get_videos_from_channel(channel_url):    
    # Set up Selenium WebDriver with headless mode
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Enable headless mode
    options.add_argument("--disable-gpu")  # Disable GPU (recommended for headless)
    options.add_argument("--window-size=1920,1080")  # Set a default window size for proper element rendering

    try:
        videos = []
        driver = webdriver.Chrome(options=options,service=Service(ChromeDriverManager().install()))
        driver.get(channel_url)
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        links=[]

        while True:
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            
            # Wait for new content to load
            time.sleep(2)  # Adjust the sleep duration if needed
            
            # Calculate new scroll height
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            
            # Break the loop if no new content is loaded
            if new_height == last_height:
                break
            last_height = new_height
        
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "contents")))
        user_data = driver.find_elements(By.XPATH,'//*[@id="video-title-link"]')        

        for i in user_data:
            href = i.get_attribute('href')
            title = i.get_attribute('title')
            links.append((href, title))

        for link, title in links:
            v_id = link.split('v=')[1]
            videos.append((v_id, title))
    finally:
        driver.quit()
            
    return videos


# Function to mark deleted transcripts
def mark_deleted_transcripts(existing_files, current_files):
    for blob in existing_files:
        if blob.name not in current_files:
            blob_client = container_client.get_blob_client(blob)
            metadata = blob_client.get_blob_properties().metadata
            metadata['IsDeleted'] = 'true'
            blob_client.set_blob_metadata(metadata)
            print(f"Marked {blob.name} as deleted.")

if __name__ == "__main__":
    # Example usage
    channel_url = os.getenv('YOUTUBE_CHANNEL_URL')
    videos = get_videos_from_channel(channel_url)
    current_files = set()

    for video_id, title in videos:
        video_url = f'https://www.youtube.com/watch?v={video_id}'
        transcript = get_transcript(video_id, video_url)
        description = get_video_description(video_url)
        filename = f'transcripts/{title}.txt'
        save_transcript_to_blob(transcript, description, filename, video_url)
        current_files.add(filename)

    # Get existing files in the container
    existing_files = container_client.list_blobs(name_starts_with='transcripts/')
    mark_deleted_transcripts(existing_files, current_files)
