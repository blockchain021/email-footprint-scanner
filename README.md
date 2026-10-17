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
   - <img width="617" height="150" alt="image" src="https://github.com/user-attachments/assets/76457ef9-ecc5-4178-a652-bba4ff18aa37" />
4. Make sure the format is **MBOX**. You can check it under
   **Multiple formats** and **All Mail data included**
   <img width="695" height="181" alt="image" src="https://github.com/user-attachments/assets/e06aa205-d5b0-42a0-a1a2-fb686bc8f0fa" />

   (the second button lets you include Spam and Trash too).
6. Click **Next step**, choose **Send download link via email**,
   and click **Create export**.
   
   <img width="736" height="230" alt="image" src="https://github.com/user-attachments/assets/8d6c46b7-9ed7-40f7-8379-8eae4f1f7eb9" />
   
8. Wait for Google's email (a few minutes to a few hours), download the
   .zip, and extract it.

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
