from __future__ import print_function
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os
import json
import re
import imaplib
import email

email_creds = None

def build_mail_service():
    #TODO: extend this for yahoo and outlook emails?

    # If modifying these scopes, delete the file token.json.
    SCOPES = ['https://www.googleapis.com/auth/gmail.labels', 'https://www.googleapis.com/auth/gmail.modify']   
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

def sort_emails(service, email_message_ids):
    # Call the Gmail API
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    label_ids = create_labels(service)

    for label in label_ids:
        gmail_msg_ids = []
        rfc822_msg_ids = email_message_ids[label]

        for rfc822_msg_id in rfc822_msg_ids:
            result = service.users().messages().list(
                userId='me',
                q='rfc822msgid:{}'.format(rfc822_msg_id)
            ).execute()
            gmail_msg_ids.append(result['messages'][0]['id'])

        for id_batch in batch(gmail_msg_ids, 1000):
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': id_batch,
                    'addLabelIds' : label_ids[label]
                }
            ).execute()

def create_labels(service):

    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])
    label_ids = {
        'Finance' : None,
        'News' : None,
        'Bills' : None
    }

    if not labels:
        print('No labels found.')
    else:
        for label_name, label_value in label_ids.items():
            found = False
            for label in labels:
                # mark label in dict if found, create it if not found
                 if label_name in label['name'] and found == False:
                     found = True
                     label_ids[label_name] = label['id']
            if not found:
                resp = service.users().labels().create(
                    userId='me', 
                    body={
                        'name': label_name,
                        'type': 'user'
                    }
                ).execute()
                label_ids[label_name] = resp['id']
    return label_ids

def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]

def main(email_message_ids):
    """
    Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    service = build_mail_service()
    sort_emails(service, email_message_ids)

def filter_emails(email_message_ids, email_data, mailbox_info):
    # puts emails into correct list depending on category
    for data in email_data:
        if isinstance(data, tuple):
            msg = email.message_from_string(str(data[1],'utf-8', errors="surrogateescape"))
            email_from = msg['from']
            message_id = msg.get('Message-ID')

            for label in mailbox_info['LABELS']:
                 if re.search(label['REGEX'], email_from):
                     email_message_ids[label['NAME']].append(message_id)
                     break

    return email_message_ids

def get_message_ids(mailbox_info):
    # searching through entirety of email box and finding message ID for specific labels for Google API
    email_message_ids = {}
    for label in mailbox_info['LABELS']:
      email_message_ids[label['NAME']] = []

    mail = imaplib.IMAP4_SSL(mailbox_info["SMTP_SERVER"])
    mail.login(
            mailbox_info["EMAIL"],
            mailbox_info["PWD"]
    )
    mail.select('inbox', readonly=True)

    #TODO: add picker that allows me to switch between ALL mail and unseen mail
    email_ids = mail.search(None, '(UNSEEN)')[1][0].split()
    email_ids_str = []

    for email_id in email_ids:
        email_ids_str.append(str(int(email_id)))
    emails_id_csv = ','.join(email_ids_str)

    resp, email_data = mail.fetch(emails_id_csv, '(RFC822)')
    if resp != 'OK':
        raise Exception("Error running imap fetch for gmail message: {0} ".format(resp))

    return filter_emails(email_message_ids, email_data, mailbox_info)
    
if __name__ == "__main__":
    #TODO argpase to determine whether or not to do all emails or specific one

    with open('email_creds.json') as json_file:
        email_creds = json.load(json_file)
    
    email_creds = email_creds['Email_Credentials']

    for mailbox_name, mailbox_info in email_creds.items():
        email_message_ids = get_message_ids(mailbox_info)
        main(email_message_ids)
