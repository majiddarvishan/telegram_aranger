# Telegram Harbor Manual Validation Checklist

This checklist covers behavior that automated tests cannot fully prove because it requires a real Telegram account, browser, and media transfer.

## Preconditions

- For YouTube feature validation before merge, work from branch `feature/youtube-download`; otherwise use `main`.
- Use a non-production Telegram account for validation.
- Configure valid `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `TELEGRAM_SESSION_ENCRYPTION_KEY`.
- If a SOCKS5 proxy is not required, disable it in the sidebar.
- Prefer an empty/test database for first validation.
- Keep browser developer tools available for download/network checks.

## 1. Web login persistence

1. Create or use a local Web account.
2. Login with **Remember me** enabled.
3. Close the browser tab.
4. Stop the Streamlit process completely.
5. Start the application again.
6. Re-open the same application URL in the same browser profile.

Expected:
- Web login is restored without asking for username/password again.
- The remembered session remains valid until logout or configured expiry.
- Logging out removes the remembered login and requires credentials again.

## 2. Telegram account restore

1. Add a Telegram account using phone/code/2FA as required.
2. Confirm dialogs load.
3. Restart the application.
4. Re-open the same Web user/account.

Expected:
- The encrypted stored Telegram session restores successfully.
- No phone code is required again unless Telegram invalidated the session.

## 3. Photo preview

Test at least:
- one small photo;
- one large/high-resolution photo;
- one photo with a caption.

For each message:
1. Load the date range containing the message.
2. Confirm the list renders without downloading the full photo automatically.
3. Click **Show Photo**.

Expected:
- A progress indicator is shown while Telegram transfer is active.
- The image appears after download.
- Caption/text remains visible.
- Tags can still be edited.
- Changing search/tag filters does not corrupt the media state.
- Re-rendering the same message reuses the valid cache.

## 4. Video playback

Test at least:
- one small MP4 video;
- one larger video;
- one video with a caption;
- one video-note if available;
- one animation/GIF if available.

For each:
1. Confirm listing the message does not download the full media automatically.
2. Click **Load Video**.
3. Observe the progress bar.

Expected:
- Progress changes from 0% toward 100% using Telegram byte progress.
- When size is known, downloaded/total size is shown.
- Video plays inline after completion.
- Caption/text remains visible.
- Cached playback does not re-download a valid copy unnecessarily.

## 5. Browser video download

1. Use a Telegram video with a recognizable filename if possible.
2. Click **Prepare Video Download** when playback has not already prepared the file.
3. Wait for completion.
4. Click **Download Video** in the browser.

Expected:
- Browser download succeeds.
- Original filename/MIME type is preserved when Telegram supplies them.
- A stable fallback filename is used otherwise.
- Downloaded file opens/plays correctly outside the application.

## 6. Interrupted download recovery

1. Start downloading a larger Telegram video.
2. Stop the Streamlit process while progress is incomplete.
3. Start the application again.
4. Return to the same message.
5. Try **Load Video** or **Prepare Video Download**.
6. Also test **Redownload Video** explicitly.

Expected:
- Stale `.part` files do not become valid cache entries.
- A size-mismatched final cache entry is rejected and removed.
- The media downloads again from Telegram.
- **Redownload Video** forces a fresh copy even when a cache entry exists.
- The final file plays correctly.

## 7. Size limits

Temporarily set a low limit such as:

```env
MEDIA_PREVIEW_MAX_MB=1
MEDIA_DOWNLOAD_MAX_MB=1
```

Try a media item larger than the configured limit.

Expected:
- The application refuses the transfer cleanly.
- The rest of the message list remains usable.
- No invalid final cache entry remains.

Restore the intended limits afterward.

## 8. Account/chat isolation

Use:
- two Telegram accounts if available;
- or at least two chats with overlapping Telegram message IDs.

Expected:
- Media cache paths do not collide across account/chat/message identity.
- Tags for the same numeric message ID in different chats remain independent.
- Switching Telegram accounts clears transient message/media view state.

## 9. Delete confirmation

1. Click **Delete** on a disposable Telegram message.
2. Cancel the confirmation.
3. Repeat and confirm deletion.

Expected:
- Cancel leaves the Telegram message unchanged.
- Confirm deletes the selected message only.
- Cached UI state for that message is removed.
- Other messages/media remain intact.

## 10. Docker smoke test with real Telegram

After local validation:

```bash
docker compose up -d --build
docker compose ps
```

Expected:
- Container becomes healthy through `/_stcore/health`.
- Web login works.
- Telegram account restore works with the persistent `/data` volume.
- Media preview/playback/download behaves the same as the local run.

## Completion rule

Only mark the remaining media-validation task complete after:
- photo preview works for small and large photos;
- inline video playback works for small and large videos;
- browser video download produces a playable file;
- interrupted-download recovery has been reproduced successfully at least once.


## 11. YouTube Download V1

Use only public content that you are permitted to save for this validation.

### Inspect

1. Open the **YouTube Download** workspace.
2. Enter one public YouTube video URL.
3. Click **Inspect**.

Expected:
- no media file is downloaded during Inspect;
- title, channel/uploader, thumbnail, duration, video ID and availability are shown;
- format/quality information is available;
- subtitle/caption tracks are visible and Manual vs Auto-generated is distinguishable;
- estimated size is shown when downloader metadata provides one;
- a rights/service notice is shown.

### Video + Audio

1. Select **Video + Audio**.
2. Test Best, max 1080p, max 720p and max 480p where the source supports them.
3. Enter a writable absolute Save directory.
4. Acknowledge the rights/service notice.
5. Start the download.

Expected:
- progress exposes phase, percentage where known, bytes, speed and ETA where available;
- merge/post-processing state is visible;
- final media path is shown;
- output basename is the sanitized YouTube title;
- an existing file is not overwritten and receives a grouped numeric suffix.

### Audio only

Repeat with **Audio only**.

Expected:
- output is an extracted audio file;
- FFmpeg/FFprobe absence is reported clearly instead of starting an invalid job.

### Manual subtitle

Use a video with a manual subtitle track.

Expected:
- selector labels the track as **Manual**;
- one selected track is downloaded;
- SRT is preferred;
- media and subtitle share exactly the same basename.

### Auto-generated caption

Use a video with auto-generated captions.

Expected:
- selector labels the track as **Auto-generated**;
- only the selected track is downloaded;
- if SRT conversion is unavailable, the actual fallback format such as VTT is reported and the file extension remains truthful.

### Save-directory safety

Validate:
- empty path;
- relative path;
- missing path without create confirmation;
- missing path with explicit create confirmation;
- non-writable directory;
- path outside configured `YOUTUBE_DOWNLOAD_ROOTS`;
- filename collision with both media and subtitle present.

Expected:
- invalid paths are rejected before downloader execution;
- output cannot escape the configured root;
- paired media/subtitle collision suffixes remain aligned.

### Docker

Build and run the container, then verify:

```bash
docker run --rm --entrypoint ffmpeg telegram-harbor:test -version
docker run --rm --entrypoint ffprobe telegram-harbor:test -version
```

Inside the application use `/data/youtube` as the Save directory.

### Windows

Verify `ffmpeg -version` and `ffprobe -version` from the same terminal, then run one Video + Audio, one Audio-only and one subtitle download using a native Windows absolute path.

### Restriction/error paths

Check representative unavailable/restricted metadata when safely reproducible.

Expected:
- stronger warning/error state is shown;
- ordinarily accessible public content remains downloadable after acknowledgement;
- private/member-only/login-protected/DRM/paywalled content is not bypassed;
- no browser-cookie import or automatic Telegram proxy reuse occurs.
