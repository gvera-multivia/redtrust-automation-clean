import logging
import imaplib, email, re
from datetime import datetime
from email.header import decode_header


class EmailFilter:
    def __init__(self, username: str, password: str, imap_server: str, date: str, log: callable, imap_port: int =993):
        self.username = username
        self.password = password
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.mail = None
        self._log = log

    def connect(self):
        """Connect to the IMAP server and login."""
        self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
        self.mail.login(self.username, self.password)

    def disconnect(self):
        """Logout and close the connection."""
        if self.mail:
            try:
                self.mail.close()
            except:
                pass
            self.mail.logout()

    @staticmethod
    def clean_text(text) -> str:
        """Clean and decode text from email headers."""
        if text is None:
            return ""
        if isinstance(text, bytes):
            try:
                return text.decode("utf-8")
            except UnicodeDecodeError:
                return text.decode("latin-1")
        return text

    @staticmethod
    def decode_email_header(header: str) -> str:
        """Decode email header."""
        decoded_header = decode_header(header)
        return ''.join([EmailFilter.clean_text(data) for data, encoding in decoded_header])

    def _get_filtered_emails(self, simple_subject_filter: str, sender_filter: str, full_subject_filter: str, full_sender_filter: str) -> list:
        """Retrieve filtered emails based on criteria."""
        if not self.mail or not isinstance(self.mail, imaplib.IMAP4_SSL):
            self.connect()
        try:
            self.mail.select("INBOX")
        except imaplib.IMAP4.error as e:
            self._log(logging.error, "EmailFilter", "Failure", f"Error selecting INBOX: {e}")
            self.connect()
            self.mail.select("INBOX")

        today = datetime.now().strftime("%d-%b-%Y")

        # Search emails by date
        status, today_data = self.mail.search(None, f'ON {today}')
        today_ids = today_data[0].split()

        if not today_ids:
            print("No emails found from today.")
            return []

        # Search emails by subject
        status, subject_data = self.mail.search(None, f'SUBJECT "{simple_subject_filter}"')
        subject_ids = subject_data[0].split() if status == "OK" else []

        # Search emails by sender
        status, sender_data = self.mail.search(None, f'FROM "{sender_filter}"')
        sender_ids = sender_data[0].split() if status == "OK" else []

        # Find intersection of all searches
        today_id_set = set([id.decode() for id in today_ids])
        subject_id_set = set([id.decode() for id in subject_ids]) if subject_ids else today_id_set
        sender_id_set = set([id.decode() for id in sender_ids]) if sender_ids else today_id_set

        initial_matches = today_id_set & subject_id_set & sender_id_set

        # Filter emails by precise criteria
        filtered_emails = []
        for email_id in initial_matches:
            status, data = self.mail.fetch(email_id.encode(), "(RFC822)")
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = self.decode_email_header(msg["Subject"])
            from_addr = self.decode_email_header(msg["From"])

            if (full_sender_filter.lower() in from_addr.lower() and
                full_subject_filter.lower() in subject.lower()):

                date_str = self.decode_email_header(msg["Date"])
                try:
                    date_obj = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
                    date_formatted = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    date_formatted = date_str

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        if "attachment" in content_disposition:
                            continue
                        if content_type == "text/plain" or content_type == "text/html":
                            try:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    body = payload.decode('utf-8', errors='replace')
                                break
                            except Exception as e:
                                print(f"Error decoding email part: {e}")
                                continue
                else:
                    try:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body = payload.decode('utf-8', errors='replace')
                    except Exception as e:
                        self._log(logging.error, "EmailFilter", "Failure", f"Error decoding email body: {e}")

                uid = None
                status, uid_data = self.mail.fetch(email_id.encode(), "(UID)")
                if status == "OK":
                    uid_string = uid_data[0].decode('utf-8', errors='replace')
                    if "UID" in uid_string:
                        uid = uid_string.split("UID")[1].strip().rstrip(")")

                email_details = {
                    "id": email_id,
                    "uid": uid,
                    "subject": subject,
                    "from": from_addr,
                    "date": date_formatted, 
                    "body": body[:500] + "..." if len(body) > 500 else body
                }
                filtered_emails.append(email_details)

        return filtered_emails

    def extract_verification_code(self, nif: str, simple_subject_filter: str, sender_filter: str, full_subject_filter: str, full_sender_filter: str) -> str | int:
        """Extract verification codes from filtered emails."""
        
        filtered_emails = self._get_filtered_emails(simple_subject_filter, sender_filter, full_subject_filter, full_sender_filter)

        if not filtered_emails:
            return None
        
        # Sort by date and get the most recent email
        most_recent = sorted(filtered_emails, key=lambda x: x['date'], reverse=True)[0]
        
        nif_segment = re.search(rf"NIF {nif}", most_recent['body'])
        if nif_segment:
            match = re.search(r"Código de validación:\s*([A-Z0-9]+)", most_recent['body'])
            if match:
                code = match.group(1)
        
        return code if code else None


def main():
    email_filter = EmailFilter(
        username="notificaciones@xvia-serviciosjuridicos.com", 
        password="Noti2017ppp56", 
        imap_server="imap.ionos.es",
        imap_port=993
    )
    email_filter.connect()
    try:
        codes = email_filter.extract_verification_code(
            nif='B16464000',
            cif='Y9416170F',
            simple_subject_filter = "Email",
            sender_filter = "noreply.dehu@correo.gob.es" ,        
            full_subject_filter = 'Verificación de Email',
            full_sender_filter = 'noreply.dehu@correo.gob.es'        
        )
    finally:
        email_filter.disconnect()
        print("Codes: ",codes)

if __name__ == "__main__":
    main()