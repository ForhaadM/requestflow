import boto3
from botocore.exceptions import ClientError

SENDER_EMAIL = "RequestFlow Notifications <notifications@requestflow-app.com>"
AWS_REGION = "us-east-1"

PRIORITY_LABELS = {
    "P0": "Urgent",
    "P1": "High",
    "P2": "Medium",
    "P3": "Low",
}


def send_review_decision_email(
    to_address: str,
    request_id: int,
    request_type: str,
    description: str,
    priority: str,
    decision: str,
    comment_text: str | None = None,
):
    """
    Sends an email notifying a requester that their request has been
    approved or rejected. Fails silently (logs, doesn't raise) so a
    notification issue never blocks the actual review from saving.
    """
    ses_client = boto3.client("ses", region_name=AWS_REGION)
    request_link = f"https://requestflow-app.com/requests/{request_id}"
    priority_label = PRIORITY_LABELS.get(priority, priority)

    if decision == "APPROVED":
        subject = f"Your request #{request_id} has been approved"
        body_text = (
            f"Good news! Your request has been approved.\n\n"
            f"Request #{request_id}\n"
            f"Type: {request_type}\n"
            f"Priority: {priority_label}\n"
            f"Description: {description}\n\n"
            f"View the full details here: {request_link}"
        )
    else:
        subject = f"Your request #{request_id} was not approved"
        body_text = (
            f"Your request was not approved.\n\n"
            f"Request #{request_id}\n"
            f"Type: {request_type}\n"
            f"Priority: {priority_label}\n"
            f"Description: {description}\n\n"
            f"Reason: {comment_text or 'No reason provided.'}\n\n"
            f"View the full details here: {request_link}"
        )

    try:
        ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [to_address]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body_text}},
            },
        )
    except ClientError as e:
        print(f"Failed to send review decision email: {e}")