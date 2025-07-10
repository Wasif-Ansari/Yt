import streamlit as st
from yt_dlp import YoutubeDL
import os, shutil, zipfile, re, tempfile

st.set_page_config(page_title="YouTube Downloader", layout="centered")
st.title("📥 YouTube Downloader")

mode = st.radio("Select download type:", ["🎬 Single Video", "📃 Playlist", "📡 Channel"], horizontal=True)
url = st.text_input("Enter YouTube URL:")

DOWNLOAD_DIR = "downloads"
ZIP_FILE = os.path.join(DOWNLOAD_DIR, "playlist_downloads.zip")

def fmt_bytes(b): return f"{b/1024/1024:.2f} MiB" if b else "N/A"
def fmt_eta(s): return f"{s//60}:{int(s%60):02}" if s else "N/A"
def sanitize_filename(title): return re.sub(r'[^\w\-_\. ]', '_', title)

def hook_factory(c): 
    prog = c.progress(0); txt = c.empty()
    def hook(d):
        if d['status'] == "downloading":
            dl, tot = d.get('downloaded_bytes', 0), d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            pct = (dl / tot) * 100 if tot else 0
            prog.progress(pct / 100)
            txt.markdown(f"⏬ {pct:.1f}% of {fmt_bytes(tot)} at {fmt_bytes(d.get('speed', 0))}/s ETA {fmt_eta(d.get('eta', 0))}")
        elif d['status'] == "finished":
            prog.progress(1.0)
            txt.markdown("✅ Download complete")
    return [hook]

def download_video(video_url, outdir, progress_container=None):
    try:
        opts = {
            'format': 'bestvideo+bestaudio',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(outdir, "%(title).200s [%(id)s].%(ext)s"),
            'quiet': True
        }
        if progress_container:
            opts['progress_hooks'] = hook_factory(progress_container)
        with YoutubeDL(opts) as ydl:
            ydl.download([video_url])
        return True, None
    except Exception as e:
        return False, str(e)

# --- Single Video Mode ---
if mode == "🎬 Single Video" and url:
    st.subheader("🎬 Single Video Download")
    with st.spinner("Fetching video info..."):
        try:
            with YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
        except Exception as e:
            st.error(f"Error fetching info: {e}")
            formats = []

    if formats:
        st.markdown(f"**Video Title:** `{info.get('title')}`")
        st.video(info.get('url'))

        video_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') == 'none']
        audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']

        compatible_pairs = []
        for v in video_formats:
            for a in audio_formats:
                if v['ext'] == a['ext']:
                    compatible_pairs.append({'video': v, 'audio': a})

        compatible_pairs.sort(key=lambda x: (
            x['video'].get('height') or 0,
            x['audio'].get('abr') or 0
        ), reverse=True)

        if not compatible_pairs:
            st.error("No compatible video/audio format pairs found.")
        else:
            video_display_list = [
                f"{pair['video'].get('height', 'N/A')}p | {pair['video']['ext']} | {pair['video']['format_id']}"
                for pair in compatible_pairs
            ]
            audio_display_list = [
                f"{pair['audio'].get('abr', 'N/A')} kbps | {pair['audio']['ext']} | {pair['audio']['format_id']}"
                for pair in compatible_pairs
            ]

            selected_idx = 0
            selected_video_display = st.selectbox("🎥 Select Video Quality:", video_display_list, index=selected_idx)
            selected_audio_display = st.selectbox("🎧 Select Audio Quality:", audio_display_list, index=selected_idx)

            selected_pair = compatible_pairs[selected_idx]
            selected_video_id = selected_pair['video']['format_id']
            selected_audio_id = selected_pair['audio']['format_id']

            col1, col2 = st.columns(2)

            with col1:
                if st.button("⬇️ Download Video with Audio"):
                    safe_title = sanitize_filename(info.get('title', 'video'))
                    filename = f"{safe_title}.mp4"
                    ydl_opts = {
                        'format': f"{selected_video_id}+{selected_audio_id}",
                        'merge_output_format': 'mp4',
                        'outtmpl': filename,
                        'quiet': True,
                        'progress_hooks': hook_factory(st.container())
                    }
                    with YoutubeDL(ydl_opts) as ydl:
                        try:
                            ydl.download([url])
                            with open(filename, "rb") as f:
                                st.success("Download finished ✅")
                                st.download_button("📥 Download Merged Video", f, file_name=filename, mime="video/mp4")
                            os.remove(filename)  # Clean up
                        except Exception as e:
                            st.error(f"Error: {e}")

            with col2:
                if st.button("⭐ Download Best Quality"):
                    safe_title = sanitize_filename(info.get('title', 'video'))
                    filename = f"{safe_title}_best.mp4"
                    ydl_opts = {
                        'format': 'bestvideo+bestaudio',
                        'merge_output_format': 'mp4',
                        'outtmpl': filename,
                        'quiet': True,
                        'progress_hooks': hook_factory(st.container())
                    }
                    with YoutubeDL(ydl_opts) as ydl:
                        try:
                            ydl.download([url])
                            with open(filename, "rb") as f:
                                st.success("Best quality video downloaded ✅")
                                st.download_button("📥 Download Best Video", f, file_name=filename, mime="video/mp4")
                            os.remove(filename)  # Clean up
                        except Exception as e:
                            st.error(f"Error: {e}")

            # Audio-only download button
            if st.button("🎵 Download Audio Only"):
                safe_title = sanitize_filename(info.get('title', 'video'))
                video_id = info.get('id', 'unknown')
                filename = f"{safe_title} [{video_id}].mp3"
                ydl_opts = {
                    'extract_audio': True,
                    'audio_format': 'mp3',
                    'format': 'bestaudio',
                    'outtmpl': filename,
                    'quiet': True,
                    'progress_hooks': hook_factory(st.container())
                }
                with YoutubeDL(ydl_opts) as ydl:
                    try:
                        ydl.download([url])
                        if os.path.exists(filename):
                            with open(filename, "rb") as f:
                                data = f.read()
                            os.remove(filename)  # Clean up
                            st.success("Audio download finished ✅")
                            st.download_button("📥 Download Audio", data, file_name=filename, mime="audio/mpeg")
                        else:
                            st.error("Failed to find downloaded audio file")
                    except Exception as e:
                        st.error(f"Error downloading audio: {e}")

# --- Playlist Mode ---
if mode == "📃 Playlist" and url:
    if st.button("📦 Download Playlist as ZIP"):
        with st.spinner("Fetching playlist info..."):
            try:
                with YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                    playlist_info = ydl.extract_info(url, download=False)
                    entries = playlist_info.get('entries', [])
                    playlist_title = sanitize_filename(playlist_info.get('title', 'playlist'))
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

        st.subheader(f"📃 Playlist: {playlist_title}")
        st.markdown("### 📄 Videos to be downloaded:")
        for idx, video in enumerate(entries, 1):
            st.write(f"{idx}. {video.get('title')}")

        with tempfile.TemporaryDirectory() as temp_dir:
            downloaded_files = []

            for idx, video in enumerate(entries, 1):
                st.markdown(f"---\n### ⏬ Downloading {idx}/{len(entries)}: **{video.get('title')}**")
                video_url = f"https://www.youtube.com/watch?v={video['id']}"
                progress_area = st.container()

                success, err = download_video(video_url, temp_dir, progress_area)
                if success:
                    downloaded_files.append(video['title'])
                else:
                    st.error(f"❌ Failed to download: {video['title']} | Error: {err}")

            zip_path = os.path.join(temp_dir, f"{playlist_title}.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file in os.listdir(temp_dir):
                    if file.endswith(".mp4"):
                        zipf.write(os.path.join(temp_dir, file), arcname=file)

            with open(zip_path, "rb") as zf:
                st.success("✅ Playlist downloaded and zipped successfully!")
                st.download_button("📦 Download ZIP", zf, file_name=f"{playlist_title}.zip")

# --- Channel Mode ---
if mode == "📡 Channel" and url:
    st.subheader("📡 Channel Download")
    batch_size = st.number_input("Enter batch size:", min_value=1, value=10, step=1)

    if 'channel_videos' not in st.session_state:
        st.session_state.channel_videos = None
    if 'batch_zips' not in st.session_state:
        st.session_state.batch_zips = []
    if 'batch_zip_dir' not in st.session_state:
        st.session_state.batch_zip_dir = tempfile.mkdtemp()

    if st.button("Fetch Channel Videos"):
        with st.spinner("Fetching channel info..."):
            try:
                with YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                    channel_info = ydl.extract_info(url, download=False)
                    entries = channel_info.get('entries', [])
                    st.session_state.channel_videos = entries
                    st.session_state.batch_zips = []
                    if entries:
                        st.success(f"Fetched {len(entries)} videos from the channel.")
                    else:
                        st.warning("No videos found in the channel.")
            except Exception as e:
                st.error(f"Error fetching channel info: {e}")

    if st.session_state.channel_videos and len(st.session_state.channel_videos) > 0:
        total_videos = len(st.session_state.channel_videos)
        st.write(f"Total videos: {total_videos}")

        if st.button("Download All Batches"):
            with st.spinner("Downloading all batches..."):
                num_batches = (total_videos + batch_size - 1) // batch_size
                for batch_idx in range(num_batches):
                    start = batch_idx * batch_size
                    end = min(start + batch_size, total_videos)
                    batch_videos = st.session_state.channel_videos[start:end]
                    st.markdown(f"### ⏬ Processing Batch {batch_idx + 1}/{num_batches}")

                    with tempfile.TemporaryDirectory() as temp_dir:
                        downloaded_files = []
                        for idx, video in enumerate(batch_videos, 1):
                            st.markdown(f"---\n#### Downloading {start + idx}/{total_videos}: **{video.get('title')}**")
                            video_url = f"https://www.youtube.com/watch?v={video['id']}"
                            progress_area = st.container()
                            success, err = download_video(video_url, temp_dir, progress_area)
                            if success:
                                downloaded_files.append(video['title'])
                            else:
                                st.error(f"❌ Failed to download: {video['title']} | Error: {err}")

                        # Create zip file
                        zip_filename = f"channel_batch_{batch_idx + 1}.zip"
                        zip_path = os.path.join(st.session_state.batch_zip_dir, zip_filename)
                        with zipfile.ZipFile(zip_path, 'w') as zipf:
                            for file in os.listdir(temp_dir):
                                if file.endswith(".mp4"):
                                    zipf.write(os.path.join(temp_dir, file), arcname=file)

                        # Store zip path for download button
                        st.session_state.batch_zips.append((batch_idx + 1, zip_path))
                        st.success(f"✅ Batch {batch_idx + 1} downloaded and zipped successfully!")

        # Display download buttons for all completed batches
        if st.session_state.batch_zips:
            st.markdown("### Completed Batches")
            for batch_num, zip_path in st.session_state.batch_zips:
                if os.path.exists(zip_path):
                    with open(zip_path, "rb") as zf:
                        st.download_button(
                            f"📦 Download Batch {batch_num} ZIP",
                            zf,
                            file_name=f"channel_batch_{batch_num}.zip"
                        )
                else:
                    st.warning(f"Batch {batch_num} ZIP file is no longer available.")
