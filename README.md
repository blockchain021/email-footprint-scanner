# Email Footprint Scanner

A Python script that lists the sites that have sent email to your inbox,
based on an .mbox file exported from Google Takeout.
Runs 100% locally: no internet, passwords, or APIs involved.

## Requirements
- Python 3 (no extra libraries needed)
- A Gmail account you own

## Usage

### 1. Export your Gmail from Google Takeout
1. Go to [takeout.google.com](https://takeout.google.com) and sign in.
2. Click **Deselect all**.
   
3. Find **Mail** and tick its checkbox.
   - Tip: press `Ctrl+F` and search for `mbox` to jump straight to it.
   <img width="617" height="150" alt="image" src="https://github.com/user-attachments/assets/76457ef9-ecc5-4178-a652-bba4ff18aa37" />

4. Click **All Mail data included** to choose which labels are exported.
   - **Recommended: leave everything included.** Signup emails often end
     up in Spam, Trash, or archived, and you want to find those too.
   - If you only care about your main inbox, untick Spam and Trash.
   
   <img width="695" height="181" alt="image" src="https://github.com/user-attachments/assets/e06aa205-d5b0-42a0-a1a2-fb686bc8f0fa" />

5. Make sure the format is **MBOX** (it is by default). Click **Next step**.

**Choose file type, frequency, and destination**

| Option | What to pick | Why |
|---|---|---|
| **Destination** | **Send download link via email** (recommended) | The file goes straight to you and never sits in another cloud. |
| | Add to Drive / Dropbox / OneDrive / Box | Only if your disk is nearly full. Your whole inbox will be stored in that cloud, so delete it afterwards. |
| **Frequency** | **Export once** (recommended) | You only need one snapshot. |
| | Every month / every 2 months for a year | Not needed. It creates 6 to 12 exports of your whole inbox. |
| **File type** | **.zip** (recommended) | Opens on almost any computer, including Windows. |
| | .tgz | Only if you are comfortable with Linux or macOS tools. |
| **File size** | **2 GB** (default) is fine for most people | Small inboxes fit in a single file. |
| | Pick a larger size (10 GB or more) | If your inbox is big, this reduces how many .zip files you get. |

6. Click **Create export**.

7. Wait for Google's email (a few minutes to a few hours). The download
   link expires after about a week, so download it soon.
   - <img width="681" height="461" alt="image" src="https://github.com/user-attachments/assets/2fad9db4-7bbc-4f73-85be-2fe2789d498b" />

8. Extract the .zip. Inside you will find the `.mbox` file.

> If you receive several .zip files, extract all of them and run the
> script once per .mbox file.

> Takeout's interface changes from time to time. If a label looks
> different, search the page for `mbox`.

### 2. Prepare the folder
Put the .mbox file and `email_footprint_scanner.py` in the same folder.
Renaming the .mbox to something simple (like `emails.mbox`) makes the
command easier to type.

### 3. Run the script
Open a terminal in that folder and run:

```
python email_footprint_scanner.py emails.mbox -o result.csv
```

If the file name has spaces, wrap it in quotes. On Windows, if `python`
isn't recognized, try `py` instead.

### 4. Review the results
Open `result.csv` in Excel or Google Sheets. Domains with signup or
password-related emails appear at the top. Use the last column to label
each domain as DELETE, KEEP, or CHANGE.

### 5. Clean up
Delete the .mbox file when you're done. It contains your entire inbox.

## What it does
- Reads only the sender, subject, and date (never the email body)
- Groups emails by domain and counts signup/password-related messages
- Generates a CSV to help you build your action list

## Limitations
- Shows who emailed you, which doesn't prove an account exists
- Can't find sites that never sent you an email

## Disclaimer
Use it only on your own email. Never upload your .mbox or your CSV files.
