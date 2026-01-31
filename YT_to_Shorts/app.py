import streamlit as st
import os
import json
import tempfile
import time
from pathlib import Path
import generateClips as gc
import cv2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page Configuration
st.set_page_config(
    page_title="AI Shorts Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if 'transcription' not in st.session_state:
    st.session_state.transcription = None
if 'clips' not in st.session_state:
    st.session_state.clips = []
if 'video_path' not in st.session_state:
    st.session_state.video_path = None
if 'temp_dir' not in st.session_state:
    # Use a fixed temporary directory to avoid permissions issues or random name changes
    base_temp = os.path.join(os.getcwd(), "temp_workspace")
    os.makedirs(base_temp, exist_ok=True)
    st.session_state.temp_dir = base_temp

# Sidebar Settings
with st.sidebar:
    st.header("⚙️ Settings")
    
    # API Key
    # Try to load from env, default to empty string
    current_api_key = os.getenv("GEMINI_API_KEY", "")
    api_key = st.text_input("Gemini API Key", value=current_api_key, type="password", help="Get one from Google AI Studio")
    
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
        # Save to .env if it changed
        if api_key != current_api_key:
            try:
                # Simple .env writer that preserves other content would be better, but for this simple app overwriting/appending is okay
                # or just appending if not exists.
                # Let's check if .env exists to decide how to write
                env_path = ".env"
                
                # Read existing lines to avoid wiping other vars if they existed (though likely none)
                lines = []
                if os.path.exists(env_path):
                    with open(env_path, "r") as f:
                        lines = f.readlines()
                
                # Update or append
                found = False
                for i, line in enumerate(lines):
                    if line.startswith("GEMINI_API_KEY="):
                        lines[i] = f"GEMINI_API_KEY={api_key}\n"
                        found = True
                        break
                
                if not found:
                    if lines and not lines[-1].endswith('\n'):
                        lines.append('\n')
                    lines.append(f"GEMINI_API_KEY={api_key}\n")
                
                with open(env_path, "w") as f:
                    f.writelines(lines)
                    
                st.toast("API Key saved persistently!")
            except Exception as e:
                st.warning(f"Could not save API key to .env: {e}")
    
    st.divider()
    
    # Model Settings
    st.subheader("🤖 AI Models")
    whisper_model = st.selectbox(
        "Whisper Model", 
        ["base", "tiny", "small", "medium", "large"],
        index=0,
        help="Larger models are more accurate but slower."
    )
    
    st.divider()
    
    # Clip Settings
    st.subheader("✂️ Clip Settings")
    
    # Combined slider for simpler UX, or separate inputs for precise control.
    # User asked to choose "how many clips i want". 
    # Usually users want a specific number, or a range.
    # Let's offer a "Target Clip Count" slider which sets both min/max to a tight range around it.
    
    target_clip_count = st.slider("Target Number of Clips", 1, 20, 5, help="How many clips should the AI try to find?")
    
    # We set min/max based on this target to give the AI some flexibility but keep it close to the user's wish.
    # e.g. if target is 5, min=4, max=6.
    min_clips = max(1, target_clip_count - 1)
    max_clips = target_clip_count + 1
    
    st.caption(f"AI will search for approximately {target_clip_count} clips (Range: {min_clips}-{max_clips})")
        
    st.divider()
    
    # Style Settings
    st.subheader("🎨 Caption Style")
    use_captions = st.toggle("Enable Captions", value=True)
    
    bg_color_hex = st.color_picker("Background Color", "#FFFFFF")
    bg_alpha = st.slider("Background Opacity", 0, 255, 230)
    
    highlight_color_hex = st.color_picker("Highlight Color", "#FFE2A5")
    highlight_alpha = st.slider("Highlight Opacity", 0, 255, 220)
    
    text_color_hex = st.color_picker("Text Color", "#000000")

    # Helper to convert hex to rgb
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    bg_color = hex_to_rgb(bg_color_hex) + (bg_alpha,)
    highlight_color = hex_to_rgb(highlight_color_hex) + (highlight_alpha,)
    text_color = hex_to_rgb(text_color_hex)

# Main Content
st.title("🎬 AI Shorts Generator")
st.markdown("Turn your long videos into engaging vertical shorts automatically.")

# Input Method Selection
input_method = st.radio("Input Source", ["Upload File", "YouTube URL"], horizontal=True)

if input_method == "YouTube URL":
    youtube_url = st.text_input("Paste YouTube URL")
    if youtube_url:
        if st.button("📥 Download Video"):
            with st.status("Downloading from YouTube...", expanded=True) as status:
                try:
                    from pytubefix import YouTube
                    
                    yt = YouTube(youtube_url)
                    status.write(f"Found video: {yt.title}")
                    
                    # Download video
                    # We download the highest resolution progressive stream (video+audio) for simplicity
                    # or separate streams if needed. For editing, a standard 720p/1080p mp4 is fine.
                    stream = yt.streams.get_highest_resolution()
                    
                    filename = f"{yt.video_id}.mp4"
                    download_path = os.path.join(st.session_state.temp_dir, filename)
                    
                    status.write("Downloading...")
                    stream.download(output_path=st.session_state.temp_dir, filename=filename)
                    
                    st.session_state.video_path = download_path
                    
                    # Try to fetch captions
                    status.write("Checking for YouTube captions...")
                    captions = gc.get_youtube_captions(yt)
                    if captions:
                        st.session_state.youtube_captions = captions
                        status.write("✅ Found YouTube captions!")
                    else:
                        st.session_state.youtube_captions = None
                        status.write("No captions found, will use Whisper.")
                        
                    status.update(label="Download complete!", state="complete", expanded=False)
                    st.success(f"Downloaded: {yt.title}")
                    
                except Exception as e:
                    st.error(f"Error downloading video: {e}")
                    status.update(label="Download failed", state="error")

elif input_method == "Upload File":
    uploaded_file = st.file_uploader("Upload a video file", type=['mp4', 'mov', 'avi', 'mkv'])
    
    if uploaded_file:
        # Save uploaded file to temp path
        temp_video_path = os.path.join(st.session_state.temp_dir, uploaded_file.name)
        with open(temp_video_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.session_state.video_path = temp_video_path
        st.session_state.youtube_captions = None # Reset captions for new file

# Common Analysis & Generation Flow
if st.session_state.video_path and os.path.exists(st.session_state.video_path):
    # Video Preview
    st.video(st.session_state.video_path)
    
    # Analyze Button
    if st.button("🚀 Analyze Video", type="primary"):
        if not api_key and not os.getenv("GEMINI_API_KEY"):
            st.error("Please provide a Gemini API Key in the sidebar.")
        else:
            with st.status("Processing video...", expanded=True) as status:
                try:
                    # Step 1: Extract Audio
                    # Only extract audio if we need it for Whisper (no captions) or if we need it for the final clip assembly
                    # Actually, we always need audio extracted for the final clip assembly (OpenCV doesn't handle audio).
                    # But we can skip it here if we have captions and move it to generation time?
                    # No, let's keep it but skip the expensive transcription if possible.
                    
                    status.write("🔊 Extracting audio...")
                    audio_path = os.path.join(st.session_state.temp_dir, "temp_audio.wav")
                    # Use the video path from session state, which is set by both download and upload methods
                    gc.extract_audio(st.session_state.video_path, audio_path)
                    
                    # Step 2: Transcribe
                    if 'youtube_captions' in st.session_state and st.session_state.youtube_captions:
                        status.write("📝 Using YouTube captions (skipping Whisper)...")
                        transcription = st.session_state.youtube_captions
                    else:
                        status.write("📝 Transcribing audio (this may take a while)...")
                        transcription = gc.transcribe_audio(audio_path, whisper_model)
                        
                    st.session_state.transcription = transcription
                    
                    # Step 3: Find Clips
                    status.write("🧠 Finding interesting moments...")
                    clip_finder = gc.LLMClipFinder(api_key=api_key)
                    suggestions = clip_finder.find_interesting_moments(
                        transcription, 
                        min_clips=min_clips, 
                        max_clips=max_clips
                    )
                    
                    if suggestions and "clips" in suggestions:
                        st.session_state.clips = suggestions["clips"]
                        status.update(label="Analysis complete!", state="complete", expanded=False)
                    else:
                        status.update(label="Analysis failed to find clips.", state="error")
                        st.error("No clips found.")
                        
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    status.update(label="Error occurred", state="error")

# Display Results & Generation Interface
if st.session_state.clips and st.session_state.video_path:
    st.divider()
    st.subheader("📋 Review & Generate Clips")
    
    # Form to select and edit clips
    with st.form("clips_form"):
        selected_clips_indices = []
        
        for i, clip in enumerate(st.session_state.clips):
            with st.expander(f"Clip {i+1}: {clip.get('start')} - {clip.get('end')}", expanded=True):
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    to_generate = st.checkbox("Generate this clip", value=True, key=f"gen_{i}")
                    if to_generate:
                        selected_clips_indices.append(i)
                    
                    # Editable timings
                    new_start = st.text_input("Start Time", value=clip.get('start'), key=f"start_{i}")
                    new_end = st.text_input("End Time", value=clip.get('end'), key=f"end_{i}")
                    
                    # Update clip data in session state if changed
                    st.session_state.clips[i]['start'] = new_start
                    st.session_state.clips[i]['end'] = new_end
                
                with col2:
                    st.info(f"**Reason:** {clip.get('reason')}")
                    st.text_area("Caption/Transcript", value=clip.get('caption', ''), height=60, key=f"cap_{i}", disabled=True)
                    
                    # Display metadata if available
                    if clip.get('title'):
                        st.markdown(f"**Title:** {clip.get('title')}")
                    if clip.get('hashtags'):
                        st.markdown(f"**Hashtags:** `{clip.get('hashtags')}`")
                    if clip.get('description'):
                        with st.expander("Description"):
                            st.write(clip.get('description'))
        
        st.divider()
        submit_btn = st.form_submit_button("🎬 Generate Selected Clips", type="primary")
        
        if submit_btn:
            if not selected_clips_indices:
                st.warning("Please select at least one clip to generate.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                generated_files = []
                
                output_dir = os.path.join(os.path.dirname(st.session_state.video_path), "generated_shorts")
                os.makedirs(output_dir, exist_ok=True)
                
                total = len(selected_clips_indices)
                
                for idx, clip_idx in enumerate(selected_clips_indices):
                    clip_data = st.session_state.clips[clip_idx]
                    status_text.text(f"Generating clip {idx+1}/{total}...")
                    
                    # Prepare segments for the clip (needed for captions)
                    if st.session_state.transcription:
                        clip_start_sec = gc.parse_timestamp(clip_data["start"])
                        clip_end_sec = gc.parse_timestamp(clip_data["end"])
                        
                        clip_segments = []
                        for segment in st.session_state.transcription:
                            if segment["end"] >= clip_start_sec and segment["start"] <= clip_end_sec:
                                import copy
                                clip_segments.append(copy.deepcopy(segment))
                        clip_data["segments"] = clip_segments
                    
                    output_path = os.path.join(output_dir, f"clip_{clip_idx+1}_{int(time.time())}.mp4")
                    
                    try:
                        final_path = gc.create_clip(
                            st.session_state.video_path,
                            clip_data,
                            output_path,
                            captions=use_captions,
                            bg_color=bg_color,
                            highlight_color=highlight_color,
                            text_color=text_color
                        )
                        if final_path:
                            generated_files.append(final_path)
                    except Exception as e:
                        st.error(f"Failed to generate clip {clip_idx+1}: {e}")
                    
                    progress_bar.progress((idx + 1) / total)
                
                status_text.text("Generation complete!")
                st.success(f"Successfully generated {len(generated_files)} clips!")
                
                # Store generated files in session state to display them outside the form
                st.session_state.generated_files = generated_files

    # Display generated clips outside the form
    if 'generated_files' in st.session_state and st.session_state.generated_files:
        st.subheader("✨ Generated Shorts")
        
        # Add a clear button to allow re-generation with new settings
        if st.button("🗑️ Clear & Regenerate"):
            st.session_state.generated_files = []
            st.rerun()

        # Iterate through generated files. 
        # Since we want to display metadata for the *generated* clips, we need to know which clip_data corresponds to which file.
        # But `generated_files` is just a list of paths.
        # The `selected_clips_indices` logic inside the form is lost here because Streamlit re-runs.
        
        # We need to MATCH generated files back to their source clip data.
        # We can do this by using a more robust heuristic or storing the metadata WITH the file path in session state.
        
        # Let's fix this properly: instead of just storing paths, let's store (path, original_clip_index) tuples.
        # But wait, `generated_files` is currently just paths. 
        # We should update the generation logic to store this info.
        
        # NOTE: Since we can't easily change the session_state structure mid-flight without breaking existing state,
        # let's try to infer it from the filename logic we used: `clip_{clip_idx+1}_{timestamp}.mp4`
        
        for i, file_path in enumerate(st.session_state.generated_files):
            with st.container():
                col_video, col_meta = st.columns([1, 1.5])
                
                with col_video:
                    # Read the video file
                    try:
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                            with open(file_path, "rb") as video_file:
                                video_bytes = video_file.read()
                                st.video(video_bytes)
                        else:
                            st.error("Video file not found or empty.")
                    except Exception as e:
                        st.error(f"Error displaying video: {e}")

                with col_meta:
                    # Try to parse index from filename
                    clip_info = None
                    try:
                        filename = os.path.basename(file_path)
                        parts = filename.split('_')
                        if len(parts) >= 3 and parts[0] == "clip":
                            # Filename format: clip_{index+1}_{timestamp}.mp4
                            # So parts[1] is index+1
                            original_idx = int(parts[1]) - 1
                            if 0 <= original_idx < len(st.session_state.clips):
                                clip_info = st.session_state.clips[original_idx]
                    except:
                        pass
                    
                    if clip_info:
                        st.subheader(f"Clip {original_idx + 1}") # Display the original clip number
                        
                        # Title
                        title = clip_info.get('title', 'No Title Generated')
                        st.markdown(f"### {title}")
                        
                        # Description
                        desc = clip_info.get('description', 'No description available.')
                        st.text_area("Description", value=desc, height=100, key=f"desc_display_{i}")
                        
                        # Hashtags
                        tags = clip_info.get('hashtags', '')
                        if tags:
                            st.info(tags)
                    else:
                        st.subheader(f"Clip {i+1}")
                        st.warning("Metadata mismatch (could not link to original clip)")

                    # Download Button
                    try:
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                            with open(file_path, "rb") as video_file:
                                video_bytes = video_file.read()
                                st.download_button(
                                    label="⬇️ Download Video",
                                    data=video_bytes,
                                    file_name=os.path.basename(file_path),
                                    mime="video/mp4",
                                    key=f"dl_btn_{i}"
                                )
                    except:
                        pass
                
                st.divider()

