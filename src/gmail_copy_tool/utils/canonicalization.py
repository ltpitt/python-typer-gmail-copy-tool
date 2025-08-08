import base64
import email
import hashlib
import logging

def compute_canonical_hash(client, msg_id):
    """
    Compute a canonical hash for a Gmail message.

    Args:
        client: Gmail client instance.
        msg_id: ID of the Gmail message.

    Returns:
        A tuple containing the canonical hash and the canonical string.
    """
    try:
        msg = client.service.users().messages().get(userId="me", id=msg_id, format="raw").execute()
        raw = msg.get("raw")
        if not raw:
            logging.getLogger(__name__).debug(f"Message {msg_id} has no raw content.")
            return None, None

        raw_bytes = base64.urlsafe_b64decode(raw.encode("utf-8"))
        parsed = email.message_from_bytes(raw_bytes)
        logging.getLogger(__name__).debug(f"Raw content for {msg_id}: {raw_bytes.decode(errors='replace')}")

        # Extract key headers for canonicalization
        key_headers = ["from", "to", "subject", "date", "message-id"]
        headers = []
        for k, v in sorted(parsed.items()):
            k_lower = k.lower().strip()
            if k_lower in key_headers:
                headers.append(f"{k_lower}: {v.strip()}")

        # Extract body parts
        body_parts = []
        if parsed.is_multipart():
            for part in parsed.walk():
                if part.is_multipart():
                    continue
                payload = part.get_payload(decode=True) or b""
                ctype = part.get_content_type()
                fname = part.get_filename() or ""
                body_parts.append(f"{ctype}||{hashlib.sha256(payload).hexdigest()}")
        else:
            payload = parsed.get_payload(decode=True) or b""
            body_parts.append(f"text/plain||{hashlib.sha256(payload).hexdigest()}")

        # Build canonical string
        canonical_string = "\n".join(headers + body_parts)
        logging.getLogger(__name__).debug(f"Canonical string for {msg_id}: {canonical_string}")

        # Compute hash
        canonical_hash = hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()
        logging.getLogger(__name__).debug(f"Canonical hash for {msg_id}: {canonical_hash}")

        return canonical_hash, canonical_string

    except Exception as e:
        logging.getLogger(__name__).error(f"Error computing canonical hash for {msg_id}: {e}", exc_info=True)
        return None, None
