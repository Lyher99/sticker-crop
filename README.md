# sticker-crop

A local Python web app for selecting sticker rectangles from image sheets and exporting full resolution PNGs. Imported images and project data stay on this computer.

## Run on Windows

Python 3.10 or newer is required. From this folder, create the virtual environment and install dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The current environment used Python 3.13.3. Stop the server with Ctrl+C.

## Use

1. Add or drop PNG, JPG/JPEG, or WebP image sheets.
2. Drag a rectangle around a sticker on the sheet. Drag in any direction; the crop is clamped to the image boundaries. Drag inside the outline to move it, or grab one of the large white handles to resize it.
3. The selection toolbar shows its source-pixel width and height. Turn on **Lock ratio** to preserve the current proportions while resizing; a new locked selection starts square. You can also type exact width and height. Press Enter or click **Extract selection**.
4. Click **Crop** beside a tray item to zoom to that sticker on its original sheet. Drag inside the outline to move it, use the handles to resize it, or choose **Draw new bounds** and drag a fresh rectangle. Save with **Save crop**. This changes which source pixels are included.
5. Click **Size** to edit the extracted sticker on the output canvas. Choose canvas width and height in the right panel, drag the artwork to position it, and use the artwork-size slider to scale it up or down. **Save size** stores this layout for that sticker without changing its crop. PNG and ZIP exports use the saved layout.
6. Use the mouse wheel to zoom around the pointer, hold Space and drag to pan, or use the zoom buttons and **Fit sheet/Fit crop/Fit canvas** controls.
7. Rename a sticker in the right tray. Click its thumbnail to download a PNG, or download all items in a ZIP. Turn on **Use custom output canvas** to export every item on a chosen canvas such as 750 by 750. Items with saved **Size** layouts retain their scale and position when the canvas dimensions match. Other items are centered and scaled to fit without stretching; unused canvas space stays transparent.

Imported sheets and extracted stickers are saved in this browser's IndexedDB storage. This keeps each browser profile's project separate instead of loading one shared server history. The browser also saves your active sheet view and unfinished crop/size editing session, so refreshing the page restores your selection and in-progress adjustments. Use **Clear sheets** to remove all imported sheets, or **Clear stickers** to remove all extracted stickers; each action asks for confirmation. Clearing sheets leaves stickers in place, but their crops can no longer be edited without the source sheets. Clearing this site's browser data also removes the project. The Python server serves the app; project images and crop history stay in the browser.

## Keyboard and export

- Enter: extract the current selection.
- Escape: clear the selection, or leave crop/size editing.
- Space + drag: pan the sheet or output canvas, like Photoshop.
- Mouse wheel or +/?: zoom. Ctrl/Cmd + +/? also zooms while the canvas is focused.
- Arrow keys: nudge the crop or output artwork by 1 pixel; Shift + arrows nudges by 10 pixels.
- F: fit the current sheet/crop/canvas to the view.
- Original-size PNG downloads retain crop dimensions and source pixels unless that sticker has a saved output layout. Custom output uses high-quality Lanczos resampling and preserves aspect ratio. ZIP entries have unique sanitized names even if tray names collide. Output-size preferences are stored in the browser.

For JPG sheets, a checkerboard pattern is part of the image pixels. Saving a crop as PNG preserves that background; it does not make it transparent. Individual crop edits change the crop bounds against the original sheet and preserve the original pixels. Erasing, background removal, Telegram resizing, multi-select, and portable project archive import/export are not included yet.
